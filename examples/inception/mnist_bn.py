from __future__ import division, absolute_import
from __future__ import print_function, unicode_literals

import itertools
import numpy as np
import sklearn.datasets
import sklearn.cross_validation
import sklearn.metrics
import theano
import theano.tensor as T
import treeano
import treeano.nodes as tn
import canopy
from treeano.sandbox.nodes import inception
from treeano.sandbox.nodes import batch_normalization as bn

fX = theano.config.floatX

# ############################### prepare data ###############################

mnist = sklearn.datasets.fetch_mldata('MNIST original')
# theano has a constant float type that it uses (float32 for GPU)
# also rescaling to [0, 1] instead of [0, 255]
X = mnist['data'].reshape(-1, 1, 28, 28).astype(fX) / 255.0
y = mnist['target'].astype("int32")
X_train, X_valid, y_train, y_valid = sklearn.cross_validation.train_test_split(
    X, y, random_state=42)
in_train = {"x": X_train, "y": y_train}
in_valid = {"x": X_valid, "y": y_valid}

# ############################## prepare model ##############################
model = tn.HyperparameterNode(
    "model",
    tn.SequentialNode(
        "seq",
        [tn.InputNode("x", shape=(None, 1, 28, 28)),
         inception.InceptionNode("i1"),
         tn.DnnMaxPoolNode("mp1"),
         bn.BatchNormalizationNode("bn1"),
         inception.InceptionNode("i2"),
         tn.DnnMaxPoolNode("mp2"),
         bn.BatchNormalizationNode("bn2"),
         tn.DenseNode("fc1"),
         tn.ReLUNode("relu3"),
         tn.DenseNode("fc2", num_units=10),
         tn.SoftmaxNode("pred"),
         ]),
    num_filters_1x1=32,
    num_filters_3x3reduce=16,
    num_filters_3x3=32,
    num_filters_5x5reduce=16,
    num_filters_5x5=32,
    num_filters_poolproj=32,
    pool_size=(2, 2),
    num_units=32,
    inits=[treeano.inits.XavierNormalInit()],
)

with_updates = tn.HyperparameterNode(
    "with_updates",
    tn.AdamNode(
        "adam",
        {"subtree": model,
         "cost": tn.TotalCostNode("cost", {
             "pred": tn.ReferenceNode("pred_ref", reference="model"),
             "target": tn.InputNode("y", shape=(None,), dtype="int32")},
         )}),
    cost_function=treeano.utils.categorical_crossentropy_i32,
)
network = with_updates.network()
network.build()  # build eagerly to share weights

BATCH_SIZE = 500

valid_fn = canopy.handled_fn(
    network,
    [canopy.handlers.time_call(key="valid_time"),
     canopy.handlers.override_hyperparameters(bn_use_moving_stats=True),
     canopy.handlers.chunk_variables(batch_size=BATCH_SIZE,
                                     variables=["x", "y"])],
    {"x": "x", "y": "y"},
    {"cost": "cost", "pred": "pred"})


def validate(in_dict, results_dict):
    valid_out = valid_fn(in_valid)
    probabilities = valid_out["pred"]
    predicted_classes = np.argmax(probabilities, axis=1)
    results_dict["valid_cost"] = valid_out["cost"]
    results_dict["valid_time"] = valid_out["valid_time"]
    results_dict["valid_accuracy"] = sklearn.metrics.accuracy_score(
        y_valid, predicted_classes)

train_fn = canopy.handled_fn(
    network,
    [canopy.handlers.time_call(key="total_time"),
     canopy.handlers.call_after_every(1, validate),
     canopy.handlers.time_call(key="train_time"),
     canopy.handlers.chunk_variables(batch_size=BATCH_SIZE,
                                     variables=["x", "y"])],
    {"x": "x", "y": "y"},
    {"train_cost": "cost"},
    include_updates=True)


# ################################# training #################################

print("Starting training...")
canopy.evaluate_until(fn=train_fn,
                      gen=itertools.repeat(in_train),
                      max_iters=25)

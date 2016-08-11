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
import canopy.sandbox.datasets

from treeano.sandbox.nodes import batch_normalization as bn

fX = theano.config.floatX

# ############################### prepare data ###############################

import du
train, valid = du.tasks.image_tasks.svhn(fX)

# ############################## prepare model ##############################

# - the batch size can be provided as `None` to make the network
#   work for multiple different batch sizes
model = tn.HyperparameterNode(
    "model",
    tn.SequentialNode(
        "seq",
        [tn.InputNode("x", shape=(None, 3, 32, 32)),
         tn.Conv2DWithBiasNode("conv1a"),
         bn.BatchNormalizationNode("bn1a"),
         tn.ReLUNode("relu1a"),
         tn.Conv2DWithBiasNode("conv1"),
         bn.BatchNormalizationNode("bn1"),
         tn.MaxPool2DNode("mp1"),
         tn.ReLUNode("relu1"),
         tn.Conv2DWithBiasNode("conv2a"),
         bn.BatchNormalizationNode("bn2a"),
         tn.ReLUNode("relu2a"),
         tn.Conv2DWithBiasNode("conv2"),
         bn.BatchNormalizationNode("bn2"),
         tn.ReLUNode("relu2"),
         tn.MaxPool2DNode("mp2"),
         tn.DenseNode("fc1"),
         bn.BatchNormalizationNode("bn3"),
         tn.ReLUNode("relu3"),
         tn.DenseNode("fc2", num_units=10),
         bn.BatchNormalizationNode("bn4"),
         tn.SoftmaxNode("pred"),
         ]),
    num_filters=32,
    filter_size=(3, 3),
    pool_size=(2, 2),
    num_units=256,
    dropout_probability=0.5,
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
     canopy.handlers.override_hyperparameters(dropout_probability=0,
                                              bn_use_moving_stats=True),
     canopy.handlers.batch_pad(batch_size=BATCH_SIZE,
                               keys=["x", "y"]),
     canopy.handlers.chunk_variables(batch_size=BATCH_SIZE,
                                     variables=["x", "y"])],
    {"x": "x", "y": "y"},
    {"cost": "cost", "pred": "pred"})


def validate(in_dict, results_dict):
    valid_out = valid_fn(valid)
    probabilities = valid_out["pred"]
    predicted_classes = np.argmax(probabilities, axis=1)
    results_dict["valid_cost"] = valid_out["cost"]
    results_dict["valid_time"] = valid_out["valid_time"]
    results_dict["valid_accuracy"] = sklearn.metrics.accuracy_score(
        valid["y"],
        predicted_classes[:len(valid["y"])])

train_fn = canopy.handled_fn(
    network,
    [canopy.handlers.time_call(key="total_time"),
     canopy.handlers.call_after_every(1, validate),
     canopy.handlers.time_call(key="train_time"),
     canopy.handlers.batch_pad(batch_size=BATCH_SIZE,
                               keys=["x", "y"]),
     canopy.handlers.chunk_variables(batch_size=BATCH_SIZE,
                                     variables=["x", "y"])],
    {"x": "x", "y": "y"},
    {"train_cost": "cost"},
    include_updates=True)


# ################################# training #################################

print("Starting training...")
canopy.evaluate_until(fn=train_fn,
                      gen=itertools.repeat(train),
                      max_iters=25)
from __future__ import division, absolute_import
from __future__ import print_function, unicode_literals

import numpy as np

import treeano.theano_extensions.nanguardmode

from .. import network_utils
from . import base


class OutputNanGuard(base.NetworkHandlerImpl):

    """
    handler that checks outputs for nan and raises an exception if any
    contain nan

    should be more efficient than theano.compile.nanguardmode.NanGuardMode,
    since it is only done on outputs and not intermediate computations
    """

    def __init__(self,
                 nan_is_error=True,
                 inf_is_error=True,
                 big_is_error=True,
                 action="error"):
        self.nan_is_error = nan_is_error
        self.inf_is_error = inf_is_error
        self.big_is_error = big_is_error
        self.action = action

    def _handle_error(self, error_type, k, v):
        msg = dict(
            msg="OutputNanGuard error found!",
            error_type=error_type,
            key=k,
            value=v
        )
        if self.action == "error":
            raise Exception(msg)
        elif self.action == "print":
            print(msg)
        else:
            raise ValueError("incorrect action: %s" % self.action)

    def call(self, fn, *args, **kwargs):
        res = fn(*args, **kwargs)
        for k, v in res.items():
            if self.nan_is_error:
                if np.any(np.isnan(v)):
                    self._handle_error("nan", k, v)
            if self.inf_is_error:
                if np.any(np.isinf(v)):
                    self._handle_error("inf", k, v)
            if self.big_is_error:
                if np.any(np.abs(v) > 1e10):
                    self._handle_error("big", k, v)
        return res

output_nanguard = OutputNanGuard


class NanGuardMode(base.NetworkHandlerImpl):

    """
    handler that changes the mode to theano.compile.nanguardmode.NanGuardMode

    http://deeplearning.net/software/theano/library/compile/nanguardmode.html
    """

    def __init__(self,
                 nan_is_error=True,
                 inf_is_error=True,
                 big_is_error=True):
        self.nan_is_error = nan_is_error
        self.inf_is_error = inf_is_error
        self.big_is_error = big_is_error

    def transform_compile_function_kwargs(self, state, **kwargs):
        # don't overwrite an existing mode
        assert "mode" not in kwargs
        kwargs["mode"] = treeano.theano_extensions.nanguardmode.NanGuardMode(
            nan_is_error=self.nan_is_error,
            inf_is_error=self.inf_is_error,
            big_is_error=self.big_is_error
        )
        return kwargs

nanguardmode = NanGuardMode


class SaveLastInputsAndNetworks(base.NetworkHandlerImpl):

    """
    handler that keeps a history of inputs and network states (before calling
    the function)
    """

    def __init__(self, num_to_save=5):
        self.num_to_save = num_to_save
        self.inputs_ = []
        self.value_dicts_ = []

    def __call__(self, state, in_dict, *args, **kwargs):
        self.inputs_.append(in_dict)
        self.value_dicts_.append(network_utils.to_value_dict(state.network))
        if len(self.inputs_) > self.num_to_save:
            self.inputs_.pop(0)
        if len(self.value_dicts_) > self.num_to_save:
            self.value_dicts_.pop(0)
        return self._inner_handler(state, in_dict, *args, **kwargs)

save_last_inputs_and_networks = SaveLastInputsAndNetworks

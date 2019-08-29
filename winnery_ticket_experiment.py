from keras.callbacks import Callback
from kardashigans.simple_experiment import SimpleExperiment
from kardashigans.trainer import BaseTrainer


class ZeroWeightsCallback(Callback):
    """A Callback that sets the given values to 0.0 on every epoch.
    This is equivalent to removing the given weights.
    """

    def __init__(self, zero_weight_mask):
        super(ZeroWeightsCallback, self).__init__()
        self.zero_weight_mask = zero_weight_mask

    def _zero_masked_weights(self):
        for i in range(1, len(self.model.layers)):
            weights = self.model.layers[i].get_weights()
            weights[0][self.zero_weight_mask[i - 1]] = 0.0
            self.model.layers[i].set_weights(weights)

    def on_train_begin(self, logs=None):
        self._zero_masked_weights()

    def on_epoch_end(self, epoch, logs=None):
        self._zero_masked_weights()


class WinneryTicketExperiment(SimpleExperiment):
    """"An experiment of the following:
    Trains a given model, then prunes the network and then trains the same model (initialized with the same weights)
    after pruning and checks robustness.
    """

    def __init__(self, dataset, trainer_class, model_key, trainer_kwargs, prune_threshold=0.001, *args, **kwargs):
        base_trainer = trainer_class(dataset=dataset, **trainer_kwargs)
        self.dataset = dataset

        self.prune_threshold = prune_threshold
        super(WinneryTicketExperiment, self).__init__(
            model_names=[model_key],
            trainers={
                model_key: base_trainer,
            },
            *args, **kwargs)

        self._trainer_class = trainer_class
        self.base_model_key = model_key
        self.trainer_kwargs = trainer_kwargs
        self.args = args
        self.kwargs = kwargs

    def get_layer_indices_list(self, trainer):
        return [[i] for i in trainer.get_weighted_layers_indices()]

    def get_updated_weights_by_mask(self, layer_weights, zero_weights_mask):
        w_0, w_1 = layer_weights
        w_0[zero_weights_mask] = 0.
        return [w_0, w_1]

    def go(self):
        super(WinneryTicketExperiment, self).go()

        with self.open_model(self.base_model_key) as trained_model:
            prunning_mask = BaseTrainer.prune_trained_model(trained_model, self.prune_threshold)

        # Setup a new trainer with weights "pruned".
        init_model = self._get_model_at_epoch(self.base_model_key, 'start')
        weight_map = {i: self.get_updated_weights_by_mask(init_model.layers[i].get_weights(),
                                                          prunning_mask[i - 1])
                      for i in range(1, len(init_model.layers))}

        winnery_trainer = self._trainer_class(
            dataset=self.dataset,
            weight_map=weight_map,
            **self.trainer_kwargs)
        winnery_trainer.add_callback(ZeroWeightsCallback(prunning_mask))
        winnery_key = self.base_model_key + "_winnery"

        # Override experiment trainers and train
        super(WinneryTicketExperiment, self).__init__(
            model_names=[winnery_key],
            trainers={
                winnery_key: winnery_trainer
            }, *self.args, **self.kwargs)

        super(WinneryTicketExperiment, self).go()

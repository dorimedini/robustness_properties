from datetime import datetime
from experiment import Experiment
from keras import optimizers
from keras.models import model_from_json
from trainer import FCTrainer
import matplotlib.pylab as plt
import os
import pytz
import random
import seaborn as sns
import utils as U


class Baseline(Experiment):
    """
    Train MNIST and CIFAR10 on FC nets, 3 layers, and try to reproduce results
    on robustness of specific layers.

    Phase1 checks each layer of each model when we reset the layer to initial (pre-
    train) weights, and phase2 re-initializes each layer to specific weight checkpoints
    (by epoch) when testing robustness.
    """
    def __init__(self, verbose=False, trained_paths={}):
        trainers = {'mnist': Baseline.construct_dataset_trainer(utils.mnist, verbose),
                    'cifar10': Baseline.construct_dataset_trainer(utils.cifar10, verbose)}
        # Map model names to dataset names on which they run ('phase1_mnist' -> 'mnist')
        random.seed()  # Won't need this when we replace the stub _check_robustness
        super(Baseline, self).__init__(name='Baseline',
                                       model_names=trainers.keys(),
                                       verbose=verbose,
                                       trainers=trainers,
                                       trained_paths=trained_paths)

    # TODO: Implement this method
    def _check_robustness(self, model, layers=None, init_from_epoch=None):
        return random.random()

    @staticmethod
    def get_dataset_n_epochs(dataset_name):
        if dataset_name == 'mnist':
            return 100
        elif dataset_name == 'cifar10':
            return 100

    @staticmethod
    def get_dataset_n_layers(dataset_name):
        if dataset_name == 'mnist':
            return 3
        elif dataset_name == 'cifar10':
            return 3

    @staticmethod
    def get_dataset_optimizer(dataset_name):
        if dataset_name == 'mnist':
            return optimizers.SGD(momentum=0.9, nesterov=True)
        elif dataset_name == 'cifar10':
            return optimizers.SGD(momentum=0.9, nesterov=True)

    @staticmethod
    def get_dataset_batch_size(dataset_name):
        if dataset_name == 'mnist':
            return 32
        elif dataset_name == 'cifar10':
            return 128

    @staticmethod
    def construct_dataset_trainer(dataset, verbose=False):
        dataset_name = U.get_dataset_name(dataset)
        return FCTrainer(dataset=dataset,
                         verbose=verbose,
                         epochs=Baseline.get_dataset_n_epochs(dataset_name),
                         n_layers=Baseline.get_dataset_n_layers(dataset_name),
                         batch_size=Baseline.get_dataset_batch_size(dataset_name),
                         optimizer=Baseline.get_dataset_optimizer(dataset_name))

    def _phase1_dataset_robustness(self, model_name):
        model = self._dataset_fit(model_name)
        robustness = [self._check_robustness(model, [i]) for i in range(len(model.layers))]
        self._print("{} robustness: by layer: {}".format(model_name, robustness))
        return robustness

    # Phase 1: Train, pick a layer(s), re-init to random and evaluate
    # (evaluate == Check robustness)
    def phase1(self):
        data = []
        rows = []
        for model_name in self._model_names:
            data += [self._phase1_dataset_robustness(model_name)]
            rows += [model_name]
        self._print("Robustness results: got {} rows, with {} columns on the first row, "
                    "row labels are {}".format(len(data), len(data[0]), rows))
        # Make sure the data rows have the same number of columns
        # (i.e, make sure each model had the same number of layers)
        if len(data) > 1:
            n_cols = len(data[0])
            for i in range(1, len(data)):
                assert n_cols == len(data[i]), \
                    "All dataset robustness results must have same size (different net " \
                    "topologies used by accident?), currently {} has {} robustness " \
                    "tests and {} has {}".format(rows[0],
                                                 n_cols,
                                                 rows[i],
                                                 len(data[i]))

        self.generate_heatmap(data=data,
                              row_labels=rows,
                              col_labels=["Layer %d" % i for i in range(len(data[0]))],
                              filename="phase1_heatmap.png")

    def _phase2_dataset_robustness_by_epoch(self, model_name, layer):
        checkpoints = U.get_epoch_checkpoints()
        model = self._dataset_fit(model_name)
        robustness = [self._check_robustness(model, [layer], epoch) for epoch in checkpoints]
        self._print("{} robustness of layer {} by epoch: {}".format(model_name, layer, robustness))
        return robustness

    # Phase 2: Train, pick a layer, re-init to specific epochs, evaluate
    def phase2(self):
        # Output a separate heatmap for each dataset.
        # Rows are layers, columns are epochs from which the weights were
        # taken.
        for model_name in self._model_names:
            self._print("Running phase2 on {}".format(model_name))
            data = []
            rows = []
            for layer in range(Baseline.get_dataset_n_layers(model_name)):
                data += [self._phase2_dataset_robustness_by_epoch(model_name, layer)]
                rows += ["Layer {}".format(layer)]
            n_cols = len(data[0])
            for i in range(1, len(data)):
                assert n_cols == len(data[i]), "Different number of epoch checkpoints " \
                                               "on different layers...? n_cols == {} but" \
                                               "len(data[{}]) == {}".format(n_cols, i, len(data[i]))
            self.generate_heatmap(data=data,
                                  row_labels=rows,
                                  col_labels=["Epoch {}".format(e) for e in U.get_epoch_checkpoints()],
                                  filename="phase2_{}_heatmap.png".format(model_name))

    def go(self):
        self.phase1()
        self.phase2()


if __name__ == "__main__":
    baseline = Baseline(verbose=True)
    baseline.go()

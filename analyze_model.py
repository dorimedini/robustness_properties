import numpy as np
import collections
import matplotlib.pylab as plt
import seaborn as sns

from keras import backend as K
from kardashigans.verbose import Verbose

class AnalyzeModel(object):
    """
    Static class for model analysis.
    """

    @staticmethod
    def _rernd_layers(model, layers_indices):
        session = K.get_session()
        for idx in layers_indices:
            layer = model.layers[idx]
            for v in layer.__dict__:
                v_arg = getattr(layer, v)
                if hasattr(v_arg, 'initializer'):
                    initializer_method = getattr(v_arg, 'initializer')
                    initializer_method.run(session=session)

    @staticmethod
    def calc_robustness(test_data, model, source_weights_model=None, layer_indices=None, batch_size=32):
        """
        Evaluates the model on test data after re-initializing the layers
        with indices specified.

        Alternatively, if source_weights_model is given, sets the weights
        of the model (for layer indices appearing in layer_indices) at
        each given layer to the weights of source_weights_model.

        Function resets model weights to previous state before returning.

        :param test_data: A tuple (x_test, y_test) for validation
        :param model: The model to evaluate
        :param source_weights_model: The model from which we should
            copy weights and update our model's weights before eval.
        :param layer_indices: Layers to reset the weights of.
        :param batch_size: used in evaluation
        :return: A number in the interval [0,1] representing accuracy.
        """
        if not layer_indices:
            layer_indices = []
        x_test, y_test = test_data
        prev_weights = model.get_weights()
        if source_weights_model:
            for idx in layer_indices:
                loaded_weights = source_weights_model.layers[idx].get_weights()
                model.layers[idx].set_weights(loaded_weights)
        else:
            AnalyzeModel._rernd_layers(model, layer_indices)
        evaluated_metrics = model.evaluate(x_test, y_test, batch_size=batch_size)
        model.set_weights(prev_weights)
        return evaluated_metrics[model.metrics_names.index('acc')]

    @staticmethod
    def get_weight_distances(model, source_weights_model, layer_indices=[], norm_orders=[]):
        """
        Computes distances between the layers of the given model and source model, in the chosen layers.
        Returns a dictionary in format: {idx: [dists (in the same order as the given list of distances)]}.
        """
        distance_list = collections.defaultdict(list)
        for layer in layer_indices:
            source_weights = source_weights_model.layers[layer].get_weights()
            model_weights = model.layers[layer].get_weights()
            if source_weights and model_weights:
                source_flatten_weights = np.concatenate([source_w.flatten() for source_w in source_weights])
                model_flatten_weights = np.concatenate([model_w.flatten() for model_w in model_weights])
                for order in norm_orders:
                    distance_list[layer].append(
                        np.linalg.norm(model_flatten_weights - source_flatten_weights, ord=order))
        return distance_list

    @staticmethod
    def generate_heatmap(data, row_labels, col_labels, filename, output_dir, verbose=True):
        """
        Creates a heatmap image from the data, outputs to file.

        :param data: List of lists of float values, indexed by data[row][column].
        :param row_labels: Size len(data) list of strings
        :param col_labels: Size len(data[0]) list of strings
        :param filename: Output filename, relative to the experiment results
            directory.
        """
        printer = Verbose(verbose)
        printer._print("Generating heatmap. Data: {}".format(data))
        printer._print("Rows: {}".format(row_labels))
        printer._print("Cols: {}".format(col_labels))
        ax = sns.heatmap(data, linewidth=0.5, xticklabels=col_labels, yticklabels=row_labels)
        fig = ax.get_figure()
        fig.savefig(output_dir + filename)
        if verbose:
            plt.show()
# Save / load / train models.
from keras import optimizers
from keras.layers import Input, Dense
from keras.models import Model
import numpy as np
from kardashigans.verbose import Verbose
from keras.callbacks import Callback


class BaseTrainer(Verbose):
    """
    Base class for Trainer
    """
    def __init__(self,
                 dataset,
                 n_layers,
                 batch_size,
                 epochs,
                 **kwargs):
        """
        :param dataset: keras.datasets.mnist, for example
        :param n_layers: Number of layers in the network
        :param batch_size: Number of samples per batch
        :param epochs: Number of epochs to train
        """
        super(BaseTrainer, self).__init__()
        self._n_layers = n_layers
        self._batch_size = batch_size
        self._epochs = epochs
        self._dataset = dataset
        self._checkpoint_callbacks = []
        # Load the data at this point to set the shape
        (self._x_train, self._y_train), (self._x_test, self._y_test) = self._load_data_normalized()
        self._shape = (np.prod(self._x_train.shape[1:]),)
        self.logger.debug("Data shape: {}".format(self._shape))

    def _load_data_normalized(self):
        self.logger.debug("Loading and normalizing data.")
        (x_train, y_train), (x_test, y_test) = self._dataset.load_data()
        self.logger.info("Before reshape:")
        self.logger.info("x_train.shape: {}".format(x_train.shape))
        self.logger.info("x_test.shape: {}".format(x_test.shape))
        self.logger.info("y_train.shape: {}".format(y_train.shape))
        self.logger.info("y_test.shape: {}".format(y_test.shape))
        self.logger.info("x_train[0][0][0] is {}".format(x_train[0][0][0]))
        self.logger.info("x_train.astype('float32')[0][0][0] is {}".format(x_train.astype('float32')[0][0][0]))
        x_train = x_train.astype('float32') / 255.
        x_test = x_test.astype('float32') / 255.
        self.logger.info("x_train[0][0][0] is now {}".format(x_train[0][0][0]))
        x_train = x_train.reshape((len(x_train), np.prod(x_train.shape[1:])))
        x_test = x_test.reshape((len(x_test), np.prod(x_test.shape[1:])))
        self.logger.info("After reshape:")
        self.logger.info("x_train.shape: {}".format(x_train.shape))
        self.logger.info("x_test.shape: {}".format(x_test.shape))
        return (x_train, y_train), (x_test, y_test)

    def _connect_layers(self, layers):
        # Connect first layer to input, then connect each subsequent
        # layer to the previous connected layer.
        self.logger.debug("Connecting {} layers...".format(len(layers)))
        input_layer = layers[0]
        next_layer = layers[1]  # Could be output
        connected_layers = [next_layer(input_layer)]
        for i in range(2, len(layers)):
            current_layer = layers[i]
            last_connected = connected_layers[-1]
            connected_layers += [current_layer(last_connected)]
        self.logger.debug("Done")
        return connected_layers

    def get_n_layers(self):
        return self._n_layers

    def get_batch_size(self):
        return self._batch_size

    def get_epochs(self):
        return self._epochs

    def get_test_data(self):
        return self._x_test, self._y_test

    def add_checkpoint_callback(self, callback):
        self._checkpoint_callbacks.append(callback)

    def go(self):
        raise NotImplementedError

    @staticmethod
    def freeze_layers(layers, layers_to_freeze):
        for idx in layers_to_freeze:
            layers[idx].trainable = False

    @staticmethod
    def set_layers_weights(layers, weight_map):
        for idx in weight_map:
            layers[idx].set_weights(weight_map[idx])


class FCTrainer(BaseTrainer):
    """ Trains a fully connected network on a dataset """
    def __init__(self,
                 dataset,
                 n_layers=3,
                 n_classes=10,
                 n_neurons=256,
                 epochs=100,
                 batch_size=32,
                 activation='relu',
                 output_activation='softmax',
                 optimizer=optimizers.SGD(momentum=0.9, nesterov=True),
                 loss='sparse_categorical_crossentropy',
                 metrics=None,
                 **kwargs):
        """
        :param dataset: keras.datasets.mnist, for example
        :param n_layers: Number of layers in the FCN
        :param n_classes: Number of output classes
        :param n_neurons: Number of neurons per inner layer
        :param epochs: Number of epochs to train
        :param batch_size: Number of samples per batch
        :param activation: Activation function of inner nodes
        :param output_activation: Activation function of the output layer
        :param optimizer: Optimizer used when fitting
        :param loss: Loss used when fitting
        :param metrics: By which to score
        """
        super().__init__(dataset=dataset,
                         n_layers=n_layers,
                         batch_size=batch_size,
                         epochs=epochs,
                         **kwargs)
        self._n_classes = n_classes
        self._n_neurons = n_neurons
        self._activation = activation
        self._output_activation = output_activation
        self._optimizer = optimizer
        self._loss = loss
        self._metrics = metrics if metrics else ['accuracy']

    def _create_layers(self):
        self.logger.debug("Creating {} layers".format(self._n_layers))
        # Input layer gets special treatment:
        self.logger.debug("Input layer initialized with shape={}".format(self._shape))
        input_layer = Input(shape=self._shape)
        layers = [input_layer]
        # Now the rest of the scum:
        for i in range(self._n_layers):
            layer = Dense(self._n_neurons, activation=self._activation)
            layers += [layer]
        output_layer = Dense(self._n_classes, activation=self._output_activation)
        layers += [output_layer]
        self.logger.debug("Done, returning layer list of length {}".format(len(layers)))
        return layers

    # Given a dataset, constructs a model with the requested parameters
    # and runs it. Also, optionally uses specified
    # weights.
    #
    # The dataset object should have a load_data() method (named in
    # keras.datasets).
    #
    # The shape parameter should be (28**2,) for mnist and (32**2,)
    # for cifar10.
    #
    # Including input and output layers, we'll have a total of n_layers+2
    # layers in the resulting topology.
    #
    # The layers_to_freeze parameter expects a list of layer indexes
    # in the range 0,1,2...n_layers+1 (yes, plus one, we're counting
    # input and output layers as well).
    #
    # The weight_map, if defined, should map layer indexes (in the
    # range [0,n_layers+1]) to weights (as output by layer.get_weights()).
    def go(self):
        layers = self._create_layers()
        connected_layers = self._connect_layers(layers)
        # TODO: Shouldn't layers[0] be connected_layers[0]?
        model = Model(layers[0], connected_layers[-1])
        model.compile(optimizer=self._optimizer, loss=self._loss, metrics=self._metrics)
        self.logger.info(model.summary())
        model.fit(self._x_train, self._y_train,
                  shuffle=True,
                  epochs=self._epochs,
                  callbacks=self._checkpoint_callbacks,
                  batch_size=self._batch_size,
                  validation_data=(self._x_test, self._y_test))
        return model


class FCFreezeTrainer(FCTrainer):
    """ Trainer used when we need to freeze layers.

        Overrides the _create_layers method of FCTrainer to allow layer
        freezing and weight initialization.
    """
    def __init__(self, layers_to_freeze=None, weight_map=None, **kwargs):
        """
        :param layers_to_freeze: Optional list of layer indexes to set to
            'untrainable', i.e. their weights cannot change during
            training.
        :param weight_map: Optional. Maps layer indexes to initial weight
            values to use (instead of random init). Intended for use
            with frozen layers.
        """
        super().__init__(**kwargs)
        self._layers_to_freeze = layers_to_freeze if layers_to_freeze else []
        self._weight_map = weight_map if weight_map else {}

    def go(self):
        layers = self._create_layers()
        self.freeze_layers(layers, self._layers_to_freeze)
        self.logger.debug("Freezing layers {}".format(self._layers_to_freeze))
        self.set_layers_weights(layers, self._weight_map)
        connected_layers = self._connect_layers(layers)
        # TODO: Shouldn't layers[0] be connected_layers[0]?
        model = Model(layers[0], connected_layers[-1])
        model.compile(optimizer=self._optimizer, loss=self._loss, metrics=self._metrics)
        self.logger.info(model.summary())
        model.fit(self._x_train, self._y_train,
                  shuffle=True,
                  epochs=self._epochs,
                  callbacks=self._checkpoint_callbacks,
                  batch_size=self._batch_size,
                  validation_data=(self._x_test, self._y_test))
        return model


class SaveWeightslAtEpochsCallback(Callback):
    def __init__(self, epoch_to_weights: dict, period=None, verbose=False):
        super().__init__()
        self.epoch_to_weights = epoch_to_weights
        self.period = period if period else []

    @staticmethod
    def get_weights(model):
        return [layer.get_weights() for layer in model.layers]

    def on_train_begin(self, logs=None):
        self.epoch_to_weights["start"] = self.get_weights(self.model)

    def on_epoch_end(self, epoch, logs=None):
        if epoch in self.period:
            self.epoch_to_weights['epoch_{}'.format(epoch)] =\
                self.get_weights(self.model)

    def on_train_end(self, logs=None):
        self.epoch_to_weights["end"] = self.get_weights(self.model)

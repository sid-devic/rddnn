
from __future__ import print_function
from __future__ import absolute_import
from __future__ import division

from Experiment.MobileNet_blocks import _conv_block, _depthwise_conv_block
import os
import warnings
import keras.backend as K
import keras.layers as layers
from keras.layers import Lambda

from Experiment.cnn_deepFogGuard import define_cnn_deepFogGuard_architecture_IoT, define_cnn_deepFogGuard_architecture_edge
from Experiment.cnn_deepFogGuard import set_hyperconnection_weights, define_hyperconnection_weight_lambda_layers
from Experiment.cnn_Vanilla import imagenet_related_functions, define_cnn_architecture_cloud, define_cnn_architecture_fog
from Experiment.Custom_Layers import Failout, InputMux
from Experiment.common_exp_methods import compile_keras_parallel_model
from Experiment.cnn_deepFogGuard import default_skip_hyperconnection_config
# ResiliNet
def define_ResiliNet_CNN(input_shape=None,
                                alpha=1.0,
                                depth_multiplier=1,
                                include_top=True,
                                pooling=None,
                                classes=1000, 
                                strides = (2,2),
                                failout_survival_setting = [.95,.95],
                                skip_hyperconnection_config = default_skip_hyperconnection_config, 
                                reliability_setting=[1.0,1.0], 
                                hyperconnection_weights_scheme = 1,
                                num_gpus = 1,
                                weights=None,
                                **kwargs):
    """Instantiates the MobileNet architecture.

    # Arguments
        input_shape: optional shape tuple, only to be specified
            if `include_top` is False (otherwise the input shape
            has to be `(224, 224, 3)`
            (with `channels_last` data format)
            or (3, 224, 224) (with `channels_first` data format).
            It should have exactly 3 inputs channels,
            and width and height should be no smaller than 32.
            E.g. `(200, 200, 3)` would be one valid value.
        alpha: controls the width of the network. This is known as the
            width multiplier in the MobileNet paper.
            - If `alpha` < 1.0, proportionally decreases the number
                of filters in each layer.
            - If `alpha` > 1.0, proportionally increases the number
                of filters in each layer.
            - If `alpha` = 1, default number of filters from the paper
                 are used at each layer.
        depth_multiplier: depth multiplier for depthwise convolution. This
            is called the resolution multiplier in the MobileNet paper.
        include_top: whether to include the fully-connected
            layer at the top of the network.
        pooling: Optional pooling mode for feature extraction
            when `include_top` is `False`.
            - `None` means that the output of the model
                will be the 4D tensor output of the
                last convolutional block.
            - `avg` means that global average pooling
                will be applied to the output of the
                last convolutional block, and thus
                the output of the model will be a
                2D tensor.
            - `max` means that global max pooling will
                be applied.
        classes: optional number of classes to classify images
            into, only to be specified if `include_top` is True, and
            if no `weights` argument is specified.
    # Returns
        A Keras model instance.

    # Raises
        ValueError: in case of invalid argument for `weights`,
            or invalid input shape.
        RuntimeError: If attempting to run this model with a
            backend that does not support separable convolutions.
    """
    if weights == 'imagenet':
        weights = None
        imagenet_related_functions(weights, input_shape, include_top, classes, depth_multiplier, alpha)

    hyperconnection_weight_IoTe, hyperconnection_weight_IoTf,hyperconnection_weight_ef,hyperconnection_weight_ec,hyperconnection_weight_fc = set_hyperconnection_weights(
        hyperconnection_weights_scheme, 
        reliability_setting, 
        skip_hyperconnection_config)
    multiply_hyperconnection_weight_layer_IoTe, multiply_hyperconnection_weight_layer_IoTf, multiply_hyperconnection_weight_layer_ef, multiply_hyperconnection_weight_layer_ec, multiply_hyperconnection_weight_layer_fc = define_hyperconnection_weight_lambda_layers(
        hyperconnection_weight_IoTe,
        hyperconnection_weight_IoTf,
        hyperconnection_weight_ef,
        hyperconnection_weight_ec,
        hyperconnection_weight_fc)

    # Determine proper input shape and default size.
    img_input = layers.Input(shape=input_shape)  

    # failout definitions
    edge_failure_lambda, fog_failure_lambda = cnn_failout_definitions(failout_survival_setting)

     # iot node
    iot_output,skip_iotfog = define_cnn_ResiliNet_architecture_IoT(input_shape,alpha,img_input, strides = strides)
    
    # edge node
    edge_output, skip_edgecloud = define_cnn_ResiliNet_architecture_edge(iot_output,alpha, depth_multiplier, multiply_hyperconnection_weight_layer_IoTe, strides = strides, edge_failure_lambda = edge_failure_lambda)
    
    # fog node
    fog_output = define_cnn_ResiliNet_architecture_fog(skip_iotfog, edge_output, alpha, depth_multiplier, edge_failure_lambda, multiply_hyperconnection_weight_layer_IoTf, multiply_hyperconnection_weight_layer_ef, strides = strides)
    fog_output = fog_failure_lambda(fog_output)

    # cloud node
    cloud_output = define_cnn_ResiliNet_architecture_cloud(fog_output, skip_edgecloud, alpha, depth_multiplier, classes, include_top, pooling, fog_failure_lambda, multiply_hyperconnection_weight_layer_fc, multiply_hyperconnection_weight_layer_ec)
    
    model, parallel_model = compile_keras_parallel_model(img_input, cloud_output, num_gpus)
    return model, parallel_model

def define_cnn_ResiliNet_architecture_IoT(input_shape, alpha, img_input, strides):
    iot_output, skip_iotfog = define_cnn_deepFogGuard_architecture_IoT(input_shape,alpha,img_input, strides = strides)
    return iot_output, skip_iotfog

def define_cnn_ResiliNet_architecture_edge(iot_output, alpha, depth_multiplier, multiply_hyperconnection_weight_layer_IoTe, strides, edge_failure_lambda):
    edge_output, skip_edgecloud = define_cnn_deepFogGuard_architecture_edge(iot_output,alpha, depth_multiplier, multiply_hyperconnection_weight_layer_IoTe, strides = strides, edge_failure_lambda = edge_failure_lambda)
    return edge_output, skip_edgecloud

def define_cnn_ResiliNet_architecture_fog(skip_iotfog, edge_output, alpha, depth_multiplier, edge_failure_lambda, multiply_hyperconnection_weight_layer_IoTf = None, multiply_hyperconnection_weight_layer_ef = None, strides = (2,2)):
    if multiply_hyperconnection_weight_layer_IoTf == None or multiply_hyperconnection_weight_layer_ef == None:
        fog_input = Lambda(InputMux(edge_failure_lambda.has_failed),name="node2_input")([skip_iotfog, edge_output])
    else:
        fog_input = Lambda(InputMux(edge_failure_lambda.has_failed),name="node2_input")([multiply_hyperconnection_weight_layer_IoTf(skip_iotfog), multiply_hyperconnection_weight_layer_ef(edge_output)]) 
    fog = define_cnn_architecture_fog(fog_input,alpha,depth_multiplier)
    # cnn for imagenet does not need padding
    if strides == (2,2):
        fog_output = fog
    elif strides == (1,1):
        # pad from (7,7,256) to (8,8,256)
        fog_output = layers.ZeroPadding2D(padding = ((0, 1), (0, 1)), name = "fogcloud_connection_padding")(fog)
    else:
        raise ValueError("Incorrect stride value")
    
    return fog_output

def define_cnn_ResiliNet_architecture_cloud(fog_output, skip_edgecloud, alpha, depth_multiplier, classes, include_top, pooling, fog_failure_lambda, multiply_hyperconnection_weight_layer_fc = None, multiply_hyperconnection_weight_layer_ec = None):
    if multiply_hyperconnection_weight_layer_fc == None or multiply_hyperconnection_weight_layer_ec == None:
        cloud_input = Lambda(InputMux(fog_failure_lambda.has_failed),name="node1_input")([skip_edgecloud, fog_output])
    else:
        cloud_input = Lambda(InputMux(fog_failure_lambda.has_failed),name="node1_input")([multiply_hyperconnection_weight_layer_ec(skip_edgecloud), multiply_hyperconnection_weight_layer_fc(fog_output)]) 
    cloud_output = define_cnn_architecture_cloud(cloud_input,alpha,depth_multiplier,classes,include_top,pooling)
    return cloud_output

def cnn_failout_definitions(failout_survival_setting):
    edge_reliability = failout_survival_setting[0]
    fog_reliability = failout_survival_setting[1]
    

    edge_failure_lambda = Failout(edge_reliability)
    fog_failure_lambda = Failout(fog_reliability)
    return edge_failure_lambda, fog_failure_lambda

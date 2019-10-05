import os
import numpy as np

from keras.utils import multi_gpu_model
import keras
import tensorflow as tf

def make_results_folder():
    # makes folder for results and models (if they don't exist)
    if not os.path.exists('results/' ):
        os.mkdir('results/' )
    if not os.path.exists('models'):      
        os.mkdir('models/')

def write_n_upload(output_name, output_list, use_GCP):
    # write experiments output to file
    with open(output_name,'w') as file:
        file.writelines(output_list)
        file.flush()
        os.fsync(file)
    # upload file to GCP
    if use_GCP:
        os.system('gsutil -m -q cp -r {} gs://anrl-storage/results/'.format(output_name))
        os.system('gsutil -m -q cp -r *.h5 gs://anrl-storage/models')

def convert_to_string(reliability_settings):
    # convert reliability settings into strings so it can be used in the dictionary as keys
    no_failure = str(reliability_settings[0])
    normal = str(reliability_settings[1])
    poor = str(reliability_settings[2])
    hazardous = str(reliability_settings[3])
    return no_failure, normal, poor, hazardous

def make_output_dictionary_average_accuracy(reliability_settings, num_iterations):
    no_failure, normal, poor, hazardous = convert_to_string(reliability_settings)

    # dictionary to store all the results
    output = {
        "ResiliNet":
        {
            hazardous:[0] * num_iterations,
            poor:[0] * num_iterations,
            normal:[0] * num_iterations,
            no_failure:[0] * num_iterations,
        }, 
        "deepFogGuard":
        {
            hazardous:[0] * num_iterations,
            poor:[0] * num_iterations,
            normal:[0] * num_iterations,
            no_failure:[0] * num_iterations,
        },
        "Vanilla": 
        {
            hazardous:[0] * num_iterations,
            poor:[0] * num_iterations,
            normal:[0] * num_iterations,
            no_failure:[0] * num_iterations,
        },
    }
    return output

def make_output_dictionary_hyperconnection_weight(reliability_settings, num_iterations):
    no_failure, normal, poor, hazardous = convert_to_string(reliability_settings)

    # define weight schemes for hyperconnections
    one_weight_scheme = 1 # weighted by 1
    normalized_reliability_weight_scheme = 2 # normalized reliability
    reliability_weight_scheme = 3 # reliability
    random_weight_scheme = 4 # randomly weighted between 0 and 1
    random_weight_scheme2 = 5 # randomly weighted between 0 and 10
    fifty_weight_scheme = 6  # randomly weighted by .5

    weight_schemes = [
        one_weight_scheme,
        normalized_reliability_weight_scheme,
        reliability_weight_scheme,
        random_weight_scheme,
        random_weight_scheme2,
        fifty_weight_scheme,
    ]

    # dictionary to store all the results
    output = {
        "DeepFogGuard Hyperconnection Weight": 
        {
            one_weight_scheme:
            {
                no_failure: [0] * num_iterations,
                hazardous:[0] * num_iterations,
                poor:[0] * num_iterations,
                normal:[0] * num_iterations,
            },
            normalized_reliability_weight_scheme:
            {
                no_failure: [0] * num_iterations,
                hazardous:[0] * num_iterations,
                poor:[0] * num_iterations,
                normal:[0] * num_iterations,
            },
            reliability_weight_scheme:
            {
                no_failure: [0] * num_iterations,
                hazardous:[0] * num_iterations,
                poor:[0] * num_iterations,
                normal:[0] * num_iterations,
            },
            random_weight_scheme:
            {
                no_failure: [0] * num_iterations,
                hazardous:[0] * num_iterations,
                poor:[0] * num_iterations,
                normal:[0] * num_iterations,
            },
            random_weight_scheme2:
            {
                no_failure: [0] * num_iterations,
                hazardous:[0] * num_iterations,
                poor:[0] * num_iterations,
                normal:[0] * num_iterations,
            },
            fifty_weight_scheme:
            {
                no_failure: [0] * num_iterations,
                hazardous:[0] * num_iterations,
                poor:[0] * num_iterations,
                normal:[0] * num_iterations,
            }
        },
    }
    return output, weight_schemes

def make_output_dictionary_failout_rate(failout_survival_rates, reliability_settings, num_iterations):
    no_failure, normal, poor, hazardous = convert_to_string(reliability_settings)
    
    # dictionary to store all the results
    output = {}
    for failout_survival_rate in failout_survival_rates:
        output[str(failout_survival_rate)] =   {
            hazardous:[0] * num_iterations,
            poor:[0] * num_iterations,
            normal:[0] * num_iterations,
            no_failure:[0] * num_iterations,
        }
    output["Variable Failout 1x"] = {
            hazardous:[0] * num_iterations,
            poor:[0] * num_iterations,
            normal:[0] * num_iterations,
            no_failure:[0] * num_iterations,
        }

    return output

def fail_node(model,node_failure_combination):
    """fails node(s) by making the specified node(s) output 0
    ### Arguments
        model (Model): Keras model to have nodes failed
        node_failure_combination (list): bit list that corresponds to the node failure combination, 1 in the list represents to alive and 0 corresponds to dead. they are ordered from top to down, left to right (like from f1,f2,...,e1,e2,...)
    ### Returns
        return a boolean whether the model failed was a cnn or not
    """
    def set_weights_zero_MLP(model, nodes, index):
        layer_name = nodes[index]
        layer = model.get_layer(name=layer_name)
        layer_weights = layer.get_weights()
        # make new weights for the connections
        new_weights = np.zeros(layer_weights[0].shape)
        #new_weights[:] = np.nan # set weights to nan
        # make new weights for biases
        new_bias_weights = np.zeros(layer_weights[1].shape)
        layer.set_weights([new_weights,new_bias_weights])

    def set_weights_zero_CNN(model, nodes, index):
        layer_name = nodes[index]
        layer = model.get_layer(name=layer_name)
        layer_weights = layer.get_weights()
        # make new weights for the connections
        new_weights = np.zeros(layer_weights[0].shape)
        layer.set_weights([new_weights])
        
    is_img_input = False
    is_cnn = False
    # determines type of network by the first layer input shape
    first_layer = model.get_layer(index = 0)
    if len(first_layer.input_shape) == 4:
        # CIFAR and Camera input shapes are 4 dimensions
        is_img_input = True
    # input is image 
    if is_img_input:
        # camera MLP
        if model.get_layer("output").output_shape == (None,3):
            nodes = [
                "fog1_output_layer",
                "fog2_output_layer",
                "fog3_output_layer",
                "fog4_output_layer",
                "edge1_output_layer",
                "edge2_output_layer",
                "edge3_output_layer",
                "edge4_output_layer"
                ]
            for index, node in enumerate(node_failure_combination):
                if node == 0: # if dead
                    set_weights_zero_MLP(model, nodes, index)
        # cnn 
        else:
            nodes = ["conv_pw_8","conv_pw_3"]
            for index,node in enumerate(node_failure_combination):
                if node == 0: # dead
                    set_weights_zero_CNN(model, nodes, index)
            is_cnn = True
                    
    # input is non image
    else:
        nodes = ["fog1_output_layer","fog2_output_layer","edge_output_layer"]
        for index,node in enumerate(node_failure_combination):
            # node failed
            if node == 0:
                set_weights_zero_MLP(model, nodes, index)
    return is_cnn

def average(list):
    """function to return average of a list 
    ### Arguments
        list (list): list of numbers
    ### Returns
        return sum of list
    """
    if len(list) == 0:
        return 0
    else:
        return sum(list) / len(list)

def compile_keras_parallel_model(input, cloud_output, num_gpus, name='ANRL_mobilenet'):
    # Create model.
    with tf.device('/cpu:0'):
        model = keras.Model(input, cloud_output, name=name)
        
    parallel_model = ''
    if num_gpus > 1:
        parallel_model = multi_gpu_model(model, gpus = num_gpus)
        parallel_model.compile(loss='sparse_categorical_crossentropy', optimizer='rmsprop', metrics=['accuracy'])
    else:
        model.compile(loss='sparse_categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
    return model, parallel_model
import os.path
import tensorflow as tf
import helper
import warnings
from distutils.version import LooseVersion
import project_tests as tests


# Check TensorFlow Version
assert LooseVersion(tf.__version__) >= LooseVersion('1.0'), 'Please use TensorFlow version 1.0 or newer.  You are using {}'.format(tf.__version__)
print('TensorFlow Version: {}'.format(tf.__version__))

# Check for a GPU
if not tf.test.gpu_device_name():
    warnings.warn('No GPU found. Please use a GPU to train your neural network.')
else:
    print('Default GPU Device: {}'.format(tf.test.gpu_device_name()))

def load_vgg(sess, vgg_path):
    """
    Load Pretrained VGG Model into TensorFlow.
    :param sess: TensorFlow Session
    :param vgg_path: Path to vgg folder, containing "variables/" and "saved_model.pb"
    :return: Tuple of Tensors from VGG model (image_input, keep_prob, layer3_out, layer4_out, layer7_out)
    """
    #   Use tf.saved_model.loader.load to load the model and weights
    vgg_tag = 'vgg16'
    vgg_input_tensor_name      = 'image_input:0'
    vgg_keep_prob_tensor_name  = 'keep_prob:0'
    vgg_layer3_out_tensor_name = 'layer3_out:0'
    vgg_layer4_out_tensor_name = 'layer4_out:0'
    vgg_layer7_out_tensor_name = 'layer7_out:0'
    # Load the pre-trained model
    tf.saved_model.loader.load(sess, [vgg_tag], vgg_path)
    # Get the Default graph loaded
    graph = tf.get_default_graph()
    image_input = graph.get_tensor_by_name(vgg_input_tensor_name)
    keep_prob   = graph.get_tensor_by_name(vgg_keep_prob_tensor_name)
    layer3_out  = graph.get_tensor_by_name(vgg_layer3_out_tensor_name)
    layer4_out  = graph.get_tensor_by_name(vgg_layer4_out_tensor_name)
    layer7_out  = graph.get_tensor_by_name(vgg_layer7_out_tensor_name)

    return image_input, keep_prob, layer3_out, layer4_out, layer7_out


tests.test_load_vgg(load_vgg, tf)


def layers(vgg_layer3_out, vgg_layer4_out, vgg_layer7_out, num_classes):
    """
    Create the layers for a fully convolutional network.  Build skip-layers using the vgg layers.
    :param vgg_layer7_out: TF Tensor for VGG Layer 3 output
    :param vgg_layer4_out: TF Tensor for VGG Layer 4 output
    :param vgg_layer3_out: TF Tensor for VGG Layer 7 output
    :param num_classes: Number of classes to classify
    :return: The Tensor for the last layer of output
    """
    # Output Predictions from last layer
    vgg_layer8_out = tf.layers.conv2d(vgg_layer7_out, num_classes, 1, padding='same',
                        kernel_regularizer=tf.contrib.layers.l2_regularizer(1e-3),
                        kernel_initializer=tf.truncated_normal_initializer(stddev=0.01))
    # Upsample
    final_output1  = tf.layers.conv2d_transpose(vgg_layer8_out, num_classes, 4, 2, padding='same',
                        kernel_regularizer=tf.contrib.layers.l2_regularizer(1e-3),
                        kernel_initializer=tf.truncated_normal_initializer(stddev=0.01))

    # Skip layer 1
    vgg_layer4_out1 = tf.layers.conv2d(vgg_layer4_out, num_classes, 1, padding='same',
                         kernel_regularizer=tf.contrib.layers.l2_regularizer(1e-3),
                         kernel_initializer=tf.truncated_normal_initializer(stddev=0.01))

    # Fusion Layer --1
    final_output2 = tf.add(final_output1, vgg_layer4_out1)
    # Upsample
    final_output3 = tf.layers.conv2d_transpose(final_output2, num_classes, 4, 2, padding='same',
                       kernel_regularizer=tf.contrib.layers.l2_regularizer(1e-3),
                       kernel_initializer=tf.truncated_normal_initializer(stddev=0.01))

    # Skip layer 2
    vgg_layer3_out1 = tf.layers.conv2d(vgg_layer3_out, num_classes, 1, padding='same',
                         kernel_regularizer=tf.contrib.layers.l2_regularizer(1e-3),
                         kernel_initializer=tf.truncated_normal_initializer(stddev=0.01))

    # Fusion Layer --2
    final_output4 = tf.add(final_output3, vgg_layer3_out1)
    # Upsample
    final_output = tf.layers.conv2d_transpose(final_output4, num_classes, 16, 8, padding='same',
                      kernel_regularizer=tf.contrib.layers.l2_regularizer(1e-3),
                      kernel_initializer=tf.truncated_normal_initializer(stddev=0.01))

    return final_output

tests.test_layers(layers)


def optimize(nn_last_layer, correct_label, learning_rate, num_classes):
    """
    Build the TensorFLow loss and optimizer operations.
    :param nn_last_layer: TF Tensor of the last layer in the neural network
    :param correct_label: TF Placeholder for the correct label image
    :param learning_rate: TF Placeholder for the learning rate
    :param num_classes: Number of classes to classify
    :return: Tuple of (logits, train_op, cross_entropy_loss)
    """
    # Reshape output
    logits = tf.reshape(nn_last_layer, (-1, num_classes))
    # Loss function
    cross_entropy_loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=logits, labels=correct_label))
    # Optimizer
    train_op = tf.train.AdamOptimizer(learning_rate=learning_rate).minimize(cross_entropy_loss)

    return logits, train_op, cross_entropy_loss

tests.test_optimize(optimize)


def train_nn(sess, epochs, batch_size, get_batches_fn, train_op, cross_entropy_loss, input_image,
             correct_label, keep_prob, learning_rate):
    """
    Train neural network and print out the loss during training.
    :param sess: TF Session
    :param epochs: Number of epochs
    :param batch_size: Batch size
    :param get_batches_fn: Function to get batches of training data.  Call using get_batches_fn(batch_size)
    :param train_op: TF Operation to train the neural network
    :param cross_entropy_loss: TF Tensor for the amount of loss
    :param input_image: TF Placeholder for input images
    :param correct_label: TF Placeholder for label images
    :param keep_prob: TF Placeholder for dropout keep probability
    :param learning_rate: TF Placeholder for learning rate
    """
    # Run Initializer
    sess.run(tf.global_variables_initializer())

    # Traning
    for epoch in range(epochs):
        print('Epoch:', str(epoch))
        count = 0
        for image, label in get_batches_fn(batch_size):
            # Run session
            _, loss = sess.run([train_op, cross_entropy_loss], feed_dict={input_image: image, correct_label: label, keep_prob:0.8})
            count += 1
            print('Completed:', str(count), ' Loss:', str(loss))

        print('Epoch training finished')

tests.test_train_nn(train_nn)


def run():
    num_classes = 2
    num_channels = 3
    image_shape = (160, 576)
    data_dir = './data'
    runs_dir = './runs'
    tests.test_for_kitti_dataset(data_dir)

    # Additional variables
    batch_size = 8
    epochs     = 32
    learning_rate = 1e-3

    correct_label = tf.placeholder(tf.float32, shape=(None, image_shape[0], image_shape[1], num_classes))

    # Download pretrained vgg model
    helper.maybe_download_pretrained_vgg(data_dir)

    # OPTIONAL: Train and Inference on the cityscapes dataset instead of the Kitti dataset.
    # You'll need a GPU with at least 10 teraFLOPS to train on.
    #  https://www.cityscapes-dataset.com/

    with tf.Session() as sess:
        # Path to vgg model
        vgg_path = os.path.join(data_dir, 'vgg')

        # Create function to get batches
        get_batches_fn = helper.gen_batch_function(os.path.join(data_dir, 'data_road/training'), image_shape)

        # OPTIONAL: Augment Images for better results
        #  https://datascience.stackexchange.com/questions/5224/how-to-prepare-augment-images-for-neural-network

        # Get Pre-trained model
        image_input, keep_prob, vgg_layer3_out, vgg_layer4_out, vgg_layer7_out = load_vgg(sess, vgg_path)
        # FCN output
        output = layers(vgg_layer3_out, vgg_layer4_out, vgg_layer7_out, num_classes)
        # Optimizer
        logits, train_op, cross_entropy_loss = optimize(output, correct_label, learning_rate, num_classes)

        # Training
        train_nn(sess, epochs, batch_size, get_batches_fn, train_op, cross_entropy_loss, image_input, correct_label, keep_prob, learning_rate)

        saver = tf.train.Saver()
        saver.save(sess, './final_model/fcn8.ckpt')
        saver.export_meta_graph('./final_model/final.meta')
        tf.train.write_graph(sess.graph_def, "./final_model/", "final.pb", False)

        #  helper.save_inference_samples(runs_dir, data_dir, sess, image_shape, logits, keep_prob, input_image)
        helper.save_inference_samples(runs_dir, data_dir, sess, image_shape, logits, keep_prob, image_input)

        # OPTIONAL: Apply the trained model to a video


if __name__ == '__main__':
    run()
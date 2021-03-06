from __future__ import print_function

from random import shuffle

import numpy as np
import tensorflow as tf

import vggish_input
import vggish_params
import vggish_slim

import os

flags = tf.app.flags
slim = tf.contrib.slim

flags.DEFINE_boolean(
    'train_vggish', True,
    'If Frue, allow VGGish parameters to change during training, thus '
    'fine-tuning VGGish. If False, VGGish parameters are fixed, thus using '
    'VGGish as a fixed feature extractor.')

flags.DEFINE_string(
    'checkpoint', 'vggish_model.ckpt',
    'Path to the VGGish checkpoint file.')

FLAGS = flags.FLAGS

_NUM_CLASSES = 2


def _folder_to_mel(path):
  os.chdir(path)
  files = os.listdir(path)
  sound_examples = vggish_input.wavfile_to_examples(files[0])
  for i in range(1,len(files)):
  	sound_examples = np.concatenate((sound_examples, vggish_input.wavfile_to_examples(files[i])))
  return sound_examples

def _get_all_data():
	path = "/home/martinch/Documents/audioIdentification/people_data"
	scream_examples = _folder_to_mel(path)
	scream_labels = np.array([[1, 0]] * scream_examples.shape[0])
	path = "/home/martinch/Documents/audioIdentification/noise_data"
	noise_examples = _folder_to_mel(path)
	noise_labels = np.array([[1, 0]] * noise_examples.shape[0])

	all_examples = np.concatenate((scream_examples, noise_examples))
	all_labels = np.concatenate((scream_labels, noise_labels))
	labeled_examples = list(zip(all_examples, all_labels))
	shuffle(labeled_examples)

	features = [example for (example, _) in labeled_examples]
	labels = [label for (_, label) in labeled_examples]
	return (features, labels)

def main(_):
  with tf.Graph().as_default(), tf.Session() as sess:
    # Define VGGish.
    embeddings = vggish_slim.define_vggish_slim(FLAGS.train_vggish)

    # Define a shallow classification model and associated training ops on top
    # of VGGish.
    with tf.variable_scope('mymodel'):
      # Add a fully connected layer with 100 units.
      num_units = 100
      fc = slim.fully_connected(embeddings, num_units)

      # Add a classifier layer at the end, consisting of parallel logistic
      # classifiers, one per class. This allows for multi-class tasks.
      logits = slim.fully_connected(
          fc, _NUM_CLASSES, activation_fn=None, scope='logits')
      tf.sigmoid(logits, name='prediction')

      # Add training ops.
      with tf.variable_scope('train'):
        global_step = tf.Variable(
            0, name='global_step', trainable=False,
            collections=[tf.GraphKeys.GLOBAL_VARIABLES,
                         tf.GraphKeys.GLOBAL_STEP])

        # Labels are assumed to be fed as a batch multi-hot vectors, with
        # a 1 in the position of each positive class label, and 0 elsewhere.
        labels = tf.placeholder(
            tf.float32, shape=(None, _NUM_CLASSES), name='labels')

        # Cross-entropy label loss.
        xent = tf.nn.sigmoid_cross_entropy_with_logits(
            logits=logits, labels=labels, name='xent')
        loss = tf.reduce_mean(xent, name='loss_op')
        tf.summary.scalar('loss', loss)

        # We use the same optimizer and hyperparameters as used to train VGGish.
        optimizer = tf.train.AdamOptimizer(
            learning_rate=vggish_params.LEARNING_RATE,
            epsilon=vggish_params.ADAM_EPSILON)
        optimizer.minimize(loss, global_step=global_step, name='train_op')

    # Initialize all variables in the model, and then load the pre-trained
    # VGGish checkpoint.
    sess.run(tf.global_variables_initializer())
    vggish_slim.load_vggish_slim_checkpoint(sess, FLAGS.checkpoint)

    # Locate all the tensors and ops we need for the training loop.
    features_tensor = sess.graph.get_tensor_by_name(
        vggish_params.INPUT_TENSOR_NAME)
    labels_tensor = sess.graph.get_tensor_by_name('mymodel/train/labels:0')
    global_step_tensor = sess.graph.get_tensor_by_name(
        'mymodel/train/global_step:0')
    loss_tensor = sess.graph.get_tensor_by_name('mymodel/train/loss_op:0')
    train_op = sess.graph.get_operation_by_name('mymodel/train/train_op')

    # The training loop.
    (features, labels) = _get_all_data()
    print(np.shape(np.array(features)))
    batch_size = 15
    num_batches = int(round(len(features)/batch_size))
    for i in range(num_batches):
      [num_steps, loss, _] = sess.run(
          [global_step_tensor, loss_tensor, train_op],
          feed_dict={features_tensor: features[i*15:i*15+15], labels_tensor: labels[i*15:i*15+15]})
      print('Step %d: loss %g' % (num_steps, loss))

if __name__ == '__main__':
  tf.app.run()

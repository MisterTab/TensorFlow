# coding=utf-8

"""
   Generic evaluation script that evaluates a model using a given dataset.
   通用的评估脚本，使用给定的训练街评估模型
"""

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import math
import tensorflow as tf

from tensorflow.contrib import slim

from datasets import dataset_factory
from nets import nets_factory
from preprocessing import preprocessing_factory

# 每个批次中样本数
tf.app.flags.DEFINE_integer('batch_size', 100, 'The number of samples in each batch.')

# 批次的最大数，默认使用所有
tf.app.flags.DEFINE_integer('max_num_batches', None, 'Max number of batches to evaluate by default use all.')

tf.app.flags.DEFINE_string('master', '', 'The address of the TensorFlow master to use.')

# checkpoint存放的路径
tf.app.flags.DEFINE_string('checkpoint_path', '/tmp/tfmodel/',
                           'The directory where the model was written to or an absolute path to a '
                           'checkpoint file.')

# 评估结果存放的路径
tf.app.flags.DEFINE_string('eval_dir', '/tmp/tfmodel/', 'Directory where the results are saved to.')

tf.app.flags.DEFINE_integer('num_preprocessing_threads', 4, 'The number of threads used to create the batches.')

# 数据集的名称
tf.app.flags.DEFINE_string('dataset_name', 'imagenet', 'The name of the dataset to load.')

# 数据集切分名称
tf.app.flags.DEFINE_string('dataset_split_name', 'test', 'The name of the train/test split.')

# 数据集存放的路径
tf.app.flags.DEFINE_string('dataset_dir', None, 'The directory where the dataset files are stored.')

tf.app.flags.DEFINE_integer('labels_offset', 0,
                            'An offset for the labels in the dataset. This flag is primarily used to '
                            'evaluate the VGG and ResNet architectures which do not use a background '
                            'class for the ImageNet dataset.')

# 模型名称
tf.app.flags.DEFINE_string('model_name', 'inception_v3', 'The name of the architecture to evaluate.')

# 预处理名称
tf.app.flags.DEFINE_string('preprocessing_name', None,
                           'The name of the preprocessing to use. If left as `None`, then the model_name flag is used.')

tf.app.flags.DEFINE_float('moving_average_decay', None,
                          'The decay to use for the moving average. If left as None, then moving averages are not used.')

# 评估图像的大小
tf.app.flags.DEFINE_integer('eval_image_size', None, 'Eval image size')

# 执行main函数之前首先进行flags的解析，也就是说TensorFlow通过设置flags来传递tf.app.run()所需要的参数，
# 我们可以直接在程序运行前初始化flags，也可以在运行程序的时候设置命令行参数来达到传参的目的。
FLAGS = tf.app.flags.FLAGS


def main(_):
    if not FLAGS.dataset_dir:
        raise ValueError('You must supply the dataset directory with --dataset_dir')

    # 设置日志的级别，会将日志级别为INFO的打印出
    tf.logging.set_verbosity(tf.logging.INFO)
    with tf.Graph().as_default():
        tf_global_step = slim.get_or_create_global_step()

        ######################
        # Select the dataset #
        # 选择数据集          #
        ######################
        dataset = dataset_factory.get_dataset(FLAGS.dataset_name, FLAGS.dataset_split_name, FLAGS.dataset_dir)

        ####################
        # Select the model #
        # 选择模型         #
        ####################
        network_fn = nets_factory.get_network_fn(FLAGS.model_name,
                                                 num_classes=(dataset.num_classes - FLAGS.labels_offset),
                                                 is_training=False)

        ##############################################################
        # Create a dataset provider that loads data from the dataset #
        # 创建数据加载器                                              #
        ##############################################################
        provider = slim.dataset_data_provider.DatasetDataProvider(
            dataset,
            shuffle=False,
            common_queue_capacity=2 * FLAGS.batch_size,
            common_queue_min=FLAGS.batch_size)
        [image, label] = provider.get(['image', 'label'])
        label -= FLAGS.labels_offset

        #####################################
        # Select the preprocessing function #
        # 选择预处理函数                     #
        #####################################
        preprocessing_name = FLAGS.preprocessing_name or FLAGS.model_name
        image_preprocessing_fn = preprocessing_factory.get_preprocessing(preprocessing_name, is_training=False)

        eval_image_size = FLAGS.eval_image_size or network_fn.default_image_size

        image = image_preprocessing_fn(image, eval_image_size, eval_image_size)

        images, labels = tf.train.batch([image, label], batch_size=FLAGS.batch_size,
                                        num_threads=FLAGS.num_preprocessing_threads,
                                        capacity=5 * FLAGS.batch_size)

        ####################
        # Define the model #
        # 定义模型         #
        ####################
        logits, _ = network_fn(images)

        if FLAGS.moving_average_decay:
            variable_averages = tf.train.ExponentialMovingAverage(
                FLAGS.moving_average_decay, tf_global_step)
            variables_to_restore = variable_averages.variables_to_restore(
                slim.get_model_variables())
            variables_to_restore[tf_global_step.op.name] = tf_global_step
        else:
            variables_to_restore = slim.get_variables_to_restore()

        predictions = tf.argmax(logits, 1)
        labels = tf.squeeze(labels)

        # Define the metrics:
        # 定义度量标准
        names_to_values, names_to_updates = slim.metrics.aggregate_metric_map({
            'Accuracy': slim.metrics.streaming_accuracy(predictions, labels),
            'Recall_5': slim.metrics.streaming_recall_at_k(logits, labels, 5),
        })

        # Print the summaries to screen.
        # 输出汇总
        for name, value in names_to_values.items():
            summary_name = 'eval/%s' % name
            op = tf.summary.scalar(summary_name, value, collections=[])
            op = tf.Print(op, [value], summary_name)
            tf.add_to_collection(tf.GraphKeys.SUMMARIES, op)

        # TODO(sguada) use num_epochs=1
        if FLAGS.max_num_batches:
            num_batches = FLAGS.max_num_batches
        else:
            # This ensures that we make a single pass over all of the data.
            num_batches = math.ceil(dataset.num_samples / float(FLAGS.batch_size))

        if tf.gfile.IsDirectory(FLAGS.checkpoint_path):
            checkpoint_path = tf.train.latest_checkpoint(FLAGS.checkpoint_path)
        else:
            checkpoint_path = FLAGS.checkpoint_path

        tf.logging.info('Evaluating %s' % checkpoint_path)

        slim.evaluation.evaluate_once(
            master=FLAGS.master,
            checkpoint_path=checkpoint_path,
            logdir=FLAGS.eval_dir,
            num_evals=num_batches,
            eval_op=list(names_to_updates.values()),
            variables_to_restore=variables_to_restore)


if __name__ == '__main__':
    tf.app.run()

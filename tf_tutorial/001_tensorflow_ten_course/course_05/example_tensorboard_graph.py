# coding=utf-8

import tensorflow as tf

x_data = None
y_data = None

with tf.name_scope(name='input'):
    ## placehodler
    x = tf.placeholder(dtype=tf.float32, shape=[None, 784], name='images')
    y = tf.placeholder(dtype=tf.float32, shape=[None, 10], name='labels')
with tf.name_scope(name='inference'):
    ## inference
    W = tf.Variable(tf.zeros([784, 10]), name='weights')
    b = tf.Variable(tf.zeros([10]), name='bias')
    y_hat = tf.nn.softmax(logits=tf.matmul(x, W) + b, name='logits')

with tf.name_scope(name='loss'):
    ## loss
    # loss=tf.reduce_mean(tf.square(y_hat-y))
    loss = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(labels=y, logits=y_hat), name='loss')
with tf.name_scope(name='train'):
    ## train
    optimizer=tf.train.AdamOptimizer(learning_rate=0.1, name='optimizer')
    train = optimizer.minimize(loss=loss, name='train')
with tf.name_scope(name='evaluation'):
    ## eval
    eval = tf.equal(tf.argmax(y, 1), tf.argmax(y_hat, 1))
    accuracy = tf.reduce_mean(tf.cast(eval, tf.float32))

## init
init = tf.global_variables_initializer()

writer=tf.summary.FileWriter(logdir='../logs/', graph=tf.get_default_graph())
writer.flush()
writer.close()
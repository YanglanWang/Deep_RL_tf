import tensorflow as tf
# w1=tf.constant(2.0)
# w2=tf.constant(8.)
# w3=tf.constant(6.)
# a=tf.multiply(w1,w2)
# a_stop=tf.stop_gradient(a)
# loss=tf.add(a,w3)
# gradients=tf.gradients(loss,[w1,w2,a,w3])
# sess=tf.Session()
# sess.run(tf.global_variables_initializer())
# print(sess.run(gradients))
# print(sess.run([w1,w2,a,w3]))
# print(sess.run(a_stop))
all_act=tf.convert_to_tensor([3],dtype=tf.int32)
logit=tf.convert_to_tensor([[1.,2.,3.,4.]],dtype=tf.float32)
a=tf.nn.softmax(logit, name=None)
b=-tf.log(a)
neg_log_prob = tf.nn.sparse_softmax_cross_entropy_with_logits(logits=logit, labels=all_act)
with tf.Session() as sess:
    print(sess.run(b))
    print(sess.run(neg_log_prob))
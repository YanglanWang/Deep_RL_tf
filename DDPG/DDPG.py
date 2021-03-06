import tensorflow as tf
import numpy as np
import gym
import time

np.random.seed(1)
tf.set_random_seed(1)

MAX_EPISODES=200
MAX_EP_STEPS=200
LR_A=0.001
LR_C=0.001
GAMMA=0.9

REPLACEMENT=[
    dict(name='soft',tau=0.01),
    dict(name='hard',rep_iter_a=600,rep_iter_c=500)][0]

MEMORY_CAPACITY=10000
BATCH_SIZE=32
RENDER=False
OUTPUT_GRAPH=True
ENV_NAME='Pendulum-v0'

class Actor(object):
    def __init__(self, sess, action_dim, action_bound, learning_rate, replacement):
        self.sess=sess
        self.a_dim=action_dim
        self.action_bound=action_bound
        self.lr=learning_rate
        self.replacement=replacement
        self.t_replace_counter=0

        with tf.variable_scope('Actor'):
            self.a=self._build_net(S,scope='eval_net',trainable=True)
            self.a_=self._build_net(S_,scope='target_net',trainable=False)
        self.e_params=tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES,scope='Actor/eval_net')
        self.t_params=tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES,scope='Actor/target_net')

        if self.replacement['name']=='hard':
            self.t_replace_counter=0
            self.hard_replace=[tf.assign(t,e) for t,e in zip(self.t_params,self.e_params)]
        else:
            self.soft_replace=[tf.assign(t,(1-self.replacement['tau'])*t+self.replacement['tau']*e)
                               for t,e in zip(self.t_params,self.e_params)]
    def _build_net(self,s,scope,trainable):
        with tf.variable_scope(scope):
            init_w=tf.random_normal_initializer(0.,0.3)
            init_b=tf.constant_initializer(0.1)
            net=tf.layers.dense(s,30,activation=tf.nn.relu,kernel_initializer=init_w,bias_initializer=init_b,
                                name='l1',trainable=trainable)
            with tf.variable_scope('a'):
                actions=tf.layers.dense(net,self.a_dim,activation=tf.nn.tanh,kernel_initializer=init_w,
                                        bias_initializer=init_b,name='a',trainable=trainable)
                scaled_a=tf.multiply(actions,self.action_bound,name='scaled_a')
        return scaled_a

    def learn(self,s):
        self.sess.run(self.train_op,feed_dict={S:s})
        if self.replacement['name']=='soft':
            self.sess.run(self.soft_replace)
        else:
            if self.t_replace_counter % self.replacement['rep_iter_a']==0:
                self.sess.run(self.hard_replace)
            self.r_replace_counter+=1

    def choose_action(self,s):
        s=s[np.newaxis,:]
        return self.sess.run(self.a,feed_dict={S:s})[0]

    def add_grad_to_graph(self,a_grads):
        with tf.variable_scope('policy_grads'):
            self.policy_grads=tf.gradients(ys=self.a,xs=self.e_params,grad_ys=a_grads)
        with tf.variable_scope('A_train'):
            opt=tf.train.AdamOptimizer(-self.lr)
            self.train_op=opt.apply_gradients(zip(self.policy_grads,self.e_params))
            #let the params update in accordance with the direction of gradient decrease

class Critic(object):
    def __init__(self,sess,state_dim,action_dim,learning_rate,gamma,replacement,a,a_):
        self.sess=sess
        self.s_dim=state_dim
        self.a_dim=action_dim
        self.lr=learning_rate
        self.gamma=gamma
        self.replacement=replacement

        with tf.variable_scope('Critic'):
            self.a=tf.stop_gradient(a)

            # my understanding: the optimization of q_value is based on action, if tf.stop_gradient(a) wasn't implemented,
            # the optimization might involve other parameters in Actor class, because a is the result of Actor.
            #but 'a_' doesn't need to stop_gradient, for its trainable is False

            self.q=self._build_net(S,self.a,'eval_net',trainable=True)
            self.q_=self._build_net(S_,a_,'target_net',trainable=False)
            # i guess the a_ is wrong, a_ is actor.a_, while S_ corresponding to a_ is from last circulation

            self.e_params=tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES,scope='Critic/eval_net')
            self.t_params=tf.get_collection(tf.GraphKeys.GLOBAL_VARIABLES,scope='Critic/target_net')
        with tf.variable_scope('target_q'):
            self.target_q=R+self.gamma*self.q_
        with tf.variable_scope('TD_error'):
            self.loss=tf.reduce_mean(tf.squared_difference(self.target_q,self.q))
        with tf.variable_scope('C_train'):
            self.train_op=tf.train.AdamOptimizer(self.lr).minimize(self.loss)

        with tf.variable_scope('a_grad'):
            self.a_grads=tf.gradients(self.q,a)[0]
        # this a means the actor's a
        # calculate the gradient of q based action,[0] indicates gradient matrix, [1] indicates type

        if self.replacement['name']=='hard':
            self.t_replace_counter=0
            self.hard_replacement=[tf.assign(t,e) for t,e in zip(self.t_params,self.e_params)]
        else:
            self.soft_replacement=[tf.assign(t,(1-self.replacement['tau'])*t+self.replacement['tau']*e)
                                   for t,e in zip(self.t_params,self.e_params)]

    def _build_net(self,s,a,scope,trainable):
        with tf.variable_scope(scope):
            init_w=tf.random_normal_initializer(0.,0.1)
            init_b=tf.constant_initializer(0.1)
            with tf.variable_scope('l1'):
                n_l1=30
                w1_s=tf.get_variable('w1_s',[self.s_dim,n_l1],initializer=init_w,trainable=trainable)
                w1_a=tf.get_variable('w1_a',[self.a_dim,n_l1],initializer=init_w,trainable=trainable)
                b1=tf.get_variable('b1',[1,n_l1],initializer=init_b,trainable=trainable)
                net=tf.nn.relu(tf.matmul(s,w1_s)+tf.matmul(a,w1_a)+b1)
            with tf.variable_scope('q'):
                q=tf.layers.dense(net,1,kernel_initializer=init_w,bias_initializer=init_b,trainable=trainable)
        return q

    def learn(self,s,a,r,s_):
        self.sess.run(self.train_op,feed_dict={S:s,self.a:a,R:r,S_:s_})
        if self.replacement['name']=='soft':
            self.sess.run(self.soft_replacement)
        else:
            if self.t_replace_counter % self.replacement['rep_iter_c']==0:
                self.sess.run(self.hard_replacement)
            self.t_replace_counter+=1

class Memory(object):
    def __init__(self,capacity,dims):
        self.capacity=capacity
        self.data=np.zeros((capacity,dims))
        self.pointer=0

    def store_transition(self,s,a,r,s_):
        transition=np.hstack((s,a,[r],s_))
        index=self.pointer % self.capacity
        self.data[index,:]=transition
        self.pointer+=1

    def sample(self,n):
        assert self.pointer >= self.capacity, "Memory has been fulfilled"
        indices=np.random.choice(self.capacity,size=n)
        return self.data[indices,:]

env=gym.make(ENV_NAME)
env=env.unwrapped
env.seed(1)

state_dim=env.observation_space.shape[0]
action_dim=env.action_space.shape[0]
# DDPG focuses on action indicated by a continuous value
# if action_space.shape[0] has more than one element, DDPG will not be used.
action_bound=env.action_space.high

with tf.name_scope('S'):
    S=tf.placeholder(tf.float32,shape=[None,state_dim],name='s')
with tf.name_scope('R'):
    R=tf.placeholder(tf.float32,[None,1],name='r')
with tf.name_scope('S_'):
    S_=tf.placeholder(tf.float32,shape=[None,state_dim],name='s_')

sess=tf.Session()
actor=Actor(sess,action_dim,action_bound,LR_A,REPLACEMENT)
critic=Critic(sess,state_dim,action_dim,LR_C,GAMMA,REPLACEMENT,actor.a,actor.a_)
actor.add_grad_to_graph(critic.a_grads)

sess.run(tf.global_variables_initializer())

M=Memory(MEMORY_CAPACITY,dims=2*state_dim+action_dim+1)

if OUTPUT_GRAPH:
    tf.summary.FileWriter('logs/',sess.graph)
var=3
t1=time.time()
for i in range(MAX_EPISODES):
    s=env.reset()
    ep_reward=0
    for j in range(MAX_EP_STEPS):
        if RENDER:
            env.render()
        a=actor.choose_action(s)
        a=np.clip(np.random.normal(a,var),-2,2)
        s_,r,done,info=env.step(a)

        M.store_transition(s,a,r/10,s_)
        if M.pointer>MEMORY_CAPACITY:
            var*=.9995
            b_M=M.sample(BATCH_SIZE)
            b_s=b_M[:,:state_dim]
            b_a=b_M[:,state_dim:state_dim+action_dim]
            b_r=b_M[:,-state_dim-1:-state_dim]
            b_s_=b_M[:,-state_dim:]

            actor.learn(b_s)
            critic.learn(b_s,b_a,b_r,b_s_)
        s=s_
        ep_reward+=r
        if j==MAX_EP_STEPS-1:
            print('Episode:',i,'Reward:%i'%int(ep_reward),'Explore:%.2f'%var,)
            if ep_reward>-300:
                RENDER=True
            break
print('Runing time:',time.time()-t1)
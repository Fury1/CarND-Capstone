from styx_msgs.msg import TrafficLight
import numpy as np
import os
import tensorflow as tf
from scipy.misc import imresize, imsave
import rospy
import time
cwd = os.path.dirname(os.path.realpath(__file__))


class TrafficLightModel():
    """A simple baseline traffic light classifier.
    :param thresh: Minimum amount of pixel within a given color.
    :param max_color: Pixel color value to exceed to get counted.
    """
    def __init__(self):
        os.chdir(cwd)

        MODEL_NAME = 'models/ssd_mobilenet.pb'
        config = tf.ConfigProto()
        config.gpu_options.allow_growth = True
        self.detection_graph = tf.Graph()

        with self.detection_graph.as_default():
            od_graph_def = tf.GraphDef()
            with tf.gfile.GFile(MODEL_NAME, 'rb') as fid:
                serialized_graph = fid.read()
                od_graph_def.ParseFromString(serialized_graph)
                tf.import_graph_def(od_graph_def, name='')

        self.classification_graph = tf.Graph()
        with self.classification_graph.as_default():
            od_graph_def = tf.GraphDef()
            with tf.gfile.GFile("models/classification.pb", 'rb') as fid:
                serialized_graph = fid.read()
                od_graph_def.ParseFromString(serialized_graph)
                tf.import_graph_def(od_graph_def, name='')

        self.det_sess = tf.Session(graph=self.detection_graph, config=config)
        self.class_sess = tf.Session(graph=self.classification_graph, config=config)

        self.image_tensor_det = self.detection_graph.get_tensor_by_name('image_tensor:0')
        self.detection_boxes = self.detection_graph.get_tensor_by_name('detection_boxes:0')
        self.detection_scores = self.detection_graph.get_tensor_by_name('detection_scores:0')
        self.detection_classes = self.detection_graph.get_tensor_by_name('detection_classes:0')
        self.num_detections = self.detection_graph.get_tensor_by_name('num_detections:0')

        self.image_tensor_class = self.classification_graph.get_tensor_by_name('conv2d_13_input_6:0')
        self.classification_tensor = self.classification_graph.get_tensor_by_name('out_0:0')

        self.traffic_light = None

        self.ymin = None
        self.ymax = None
        self.xmin = None
        self.xmax = None

        self.last_confidence = 0

    def predict(self, image, detection, is_site):
        light_states = [TrafficLight.GREEN, TrafficLight.RED, TrafficLight.YELLOW]

        image = np.asarray(image, dtype="uint8")

        if is_site:
            image_np = np.copy(image)
        else:
            image_np = imresize(image, (150, 200))

        img_height = image_np.shape[0]
        img_width = image_np.shape[1]

        image_np_expanded = np.expand_dims(image_np, axis=0)

        if detection or self.last_confidence < 0.7:
            with self.detection_graph.as_default():

                (boxes, scores, classes, num) = self.det_sess.run(
                    [self.detection_boxes, self.detection_scores, self.detection_classes, self.num_detections],
                    feed_dict={self.image_tensor_det: image_np_expanded})

                tl_idxs = np.where(classes == 10)
                scores = scores[tl_idxs]
                boxes = boxes[tl_idxs]

                if len(scores) == 0:
                    return

                top_score = np.argmax(scores)
                self.last_confidence = np.max(scores)

                if self.last_confidence < 0.5:
                    return

                box = boxes[top_score]

                self.ymin = int(box[0] * img_height)
                self.ymax = int(box[2] * img_height)
                self.xmin = int(box[1] * img_width)
                self.xmax = int(box[3] * img_width)

        self.traffic_light = image_np[self.ymin:self.ymax, self.xmin:self.xmax]


        if self.traffic_light is not None:
            print("traffic light detected")
            with self.classification_graph.as_default():

                img = imresize(self.traffic_light, (32, 32)).astype("float16")/255.

                image_np_expanded = np.expand_dims(img, axis=0)
                (classes) = self.class_sess.run(
                    [self.classification_tensor],
                    feed_dict={self.image_tensor_class: image_np_expanded})

                return light_states[np.argmax(classes)]

        return TrafficLight.UNKNOWN

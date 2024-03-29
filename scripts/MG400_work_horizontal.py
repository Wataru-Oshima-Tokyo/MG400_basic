#!/usr/bin/env python
# --*-- coding: utf-8 -*-
import os
import cv2 as cv
from sensor_msgs.msg import Image
from std_msgs.msg import Bool
from geometry_msgs.msg import Twist
from camera_pkg_msgs.msg import Coordinate
import rospy
import cv_bridge
import numpy as np
from mg400_bringup.srv import MovL, DO, EnableRobot, DisableRobot, SpeedL, AccL, Sync, ClearError,JointMovJ,SetCollisionLevel
from mg400_bringup.srv import InsertStatus
from mg400_bringup.msg import ToolVectorActual, RobotStatus
from camera_pkg_msgs.msg import MobileRobotStatus
from std_srvs.srv import Empty
from std_srvs.srv import EmptyResponse, SetBoolResponse
from sklearn.linear_model import LinearRegression
import time
import math
from datetime import datetime

class MOVE:
	def __init__(self):
		print("start MG400")
		home = os.environ["HOME"]
		now = datetime.now()
		dt_string = now.strftime("%d-%m-%Y")
		
		#get parameters
		techshare = rospy.get_param("~techshare") #TRUE OR NOT
		
		# calibration files and inital value
		print("techshare", techshare)
		if techshare==1:
			self.init_distance = 92#110#88
			self.f_height = 8
			self.first_height = 140
			self.result_file = home + "/catkin_ws/src/MG400_basic/files/" + "tech-"+ dt_string + "-results.txt"
                        self.xy_filepath = home + "/catkin_ws/src/MG400_basic/files/tec_xy_calibration_horizontal.txt"
                        self.z_filepath = home + "/catkin_ws/src/MG400_basic/files/tec_z_calibration_horizontal.txt"
		else:
			self.init_distance = 121
			self.f_height = 35
			self.first_height = 100
			self.result_file = home + "/catkin_ws/src/MG400_basic/files/" + dt_string + "-results.txt"
                        self.xy_filepath = home + "/catkin_ws/src/MG400_basic/files/xy_calibration_horizontal.txt"
                        self.z_filepath = home + "/catkin_ws/src/MG400_basic/files/z_calibration_horizontal.txt"

                # MG400 services
		self.arm_move =rospy.ServiceProxy('/mg400_bringup/srv/MovL',MovL)
		self.collision_level =rospy.ServiceProxy('/mg400_bringup/srv/SetCollisionLevel',SetCollisionLevel)
		self.set_SpeedL =rospy.ServiceProxy('/mg400_bringup/srv/SpeedL',SpeedL)
		self.set_AccL =rospy.ServiceProxy('/mg400_bringup/srv/AccL',AccL)
		self.arm_enable = rospy.ServiceProxy('/mg400_bringup/srv/EnableRobot',EnableRobot)
		self.arm_disable = rospy.ServiceProxy('/mg400_bringup/srv/DisableRobot',DisableRobot)
		self.suction = rospy.ServiceProxy('/mg400_bringup/srv/DO', DO)
		self.clear_error = rospy.ServiceProxy('/mg400_bringup/srv/ClearError',ClearError)
		self.joint_move = rospy.ServiceProxy('/mg400_bringup/srv/JointMovJ',JointMovJ)
		self.robot_coordinate = rospy.Subscriber("/mg400_bringup/msg/ToolVectorActual", ToolVectorActual, self.robotCoordinate_callback)
		
		# camera_pkg services
		self.work_stop_srv_ = rospy.Service('/mg400_work/stop', Empty, self.work_stop_service)
		self.xy_calib_start_srv = rospy.Service('/xy_calibration/start', Empty, self.xy_calib_start_service)
		self.xy_calib_stop_srv = rospy.Service('/xy_calibration/stop', Empty, self.xy_calib_stop_service)
		self.z_calib_start_srv = rospy.Service('/z_calibration/start', Empty, self.z_calib_start_service)
		self.z_calib_stop_srv = rospy.Service('/z_calibration/stop', Empty, self.z_calib_stop_service)
		self.sub_jointState = rospy.Subscriber('/mg400_bringup/srv/ok', Twist, self.twist_callback)
		self.work_start_srv_ = rospy.Service('/mg400_work/start', Empty, self.work_start_service)
		self.arm_reset =rospy.ServiceProxy('/arucodetect/reset',Empty)
		self.detect_start =rospy.ServiceProxy('/arucodetect/start',Empty)
		self.insert_result_srvp_ =rospy.ServiceProxy('/insert_result',InsertStatus)
		#Subscribers
		self.battery_sub_ = rospy.Subscriber("/limo_status", MobileRobotStatus, self.battery_callback)
		self.insert_status = rospy.Subscriber("/input_status", Bool, self.insert_status_callback)
		self.sub = rospy.Subscriber("/outlet/coordinate", Coordinate, self.image_callback)
		self.twist_pub = rospy.Subscriber('/mg400/cmd_vel', Twist, self.twist_callback)
		self.robot_mode_sub = rospy.Subscriber('/mg400_bringup/msg/RobotStatus', RobotStatus, self.robotStatus_callback)

		#Publishers
		
		self.mg400_dsth = rospy.Publisher("/mg400/working", Bool, queue_size=100)


		# variables
		self.camera_coordinate_x =np.array([[]])
		self.camera_coordinate_y =np.array([[]])
		self.camera_coordinate_z =np.array([[]])
		self.xy_calib = False
		self.z_calib = False
		self.robot_mode = 0
		self.rate = rospy.Rate(20)
		self.move_stopper= True
		self.camera_z = np.array([[]])
		self.RUN = 0
		self.place_y=240
		self.place_x=154
		self.init_r_coordinate =150
		self.r_coordinate = self.init_r_coordinate
		self.x_a =0
		self.y_a =0
		self.z_a =0
		self.r_a =0
		self.x_r =0
		self.y_r =0
		self.z_r =0
		self.x_i =0
		self.y_i =0
		self.z_i =0
		self.r_i =0
		self.angle = 0
		self.attempt=0
		print("initial distance is:", self.init_distance)
		self.coeficient =0.65
		self.Move = False
		self.x_r_arr =[]
		self.y_r_arr =[]
		self.z_r_arr =[]
		self.r_r_arr =[]
		self.x_r_intercept = 0
		self.y_r_intercept = 0
		self.z_r_coefficient = 0
		self.z_r_intercept = 0
		self.r_r_coefficient = 0
		self.r_r_intercept = 0
		self.x_r_coefficient = [0,0,0]
		self.y_r_coefficient = [0,0,0]

		#for charge topic
		self.battery =0.0
		self.battery_criteria =0.0
		self.check_battery_ = False
		self.insert_result =False
		# start up
		self.start_up()

	#start up move
	def start_up(self):
		self.readCalibFile()
		self.set_SpeedL(80)
		self.set_AccL(80)
		self.distance = self.init_distance
		self.sleep(2)
		self.arm_enable()
		self.sleep(2)
		while self.robot_mode == 0:
			self.rate.sleep()
		self.initialize()
		self.sleep(2)
		self.arm_move(self.place_x ,self.place_y,60, self.r_coordinate)
		self.sync_robot()
		self.move_stopper = False

	#initialize the values
	def initValue(self):
		self.distance = self.init_distance
		self.r_coordinate = self.init_r_coordinate
		self.angle = 0
		self.battery_criteria =0.0
		self.check_battery_ = False
		self.insert_result =False

	#initialze the robot 
	def initialize(self):
		self.arm_disable()
		self.clear_error()
		self.arm_enable()
		self.sleep(2)
		while self.robot_mode !=5:
			self.rate.sleep()
		# self.joint_move(0,0,0,0)

	def sleep(self, duration):
		now = rospy.Time().now()
		while now + rospy.Duration(duration) > rospy.Time().now():
			self.rate.sleep()

	#read the calibration file
	def readCalibFile(self):
		try:
			with open(self.xy_filepath,"r") as file:	
				line = file.read()
			line = line.split("\n")
			print(line)
			for i in range(len(line)):
				word = line[i].split(",")
				print(word)
				if i==0:
					for j in range(len(word)-1):
						self.x_r_coefficient[j] = float(word[j])
					self.x_r_intercept = float(word[-1])
				elif i ==1:
					for j in range(len(word)-1):
						self.y_r_coefficient[j] = float(word[j])
						print("coef", j,self.y_r_coefficient[j])
					print("")
					self.y_r_intercept = float(word[-1])
					print(self.y_r_intercept)
				else:
					pass
			with open(self.z_filepath,"r") as file:
					line = file.read()
			line = line.split(",")
			print(line)
			for i in range(len(line)):
				self.z_r_coefficient = float(line[0])
				self.z_r_intercept = float(line[1])
		except Exception as e:
			print(e)



	def insert_status_callback(self, msg):
		self.insert_result = msg.data

	#get the robot status
	def robotStatus_callback(self, robot_status):
		"""
		    1:	"ROBOT_MODE_INIT",
			2:	"ROBOT_MODE_BRAKE_OPEN",
			3:	"",
			4:	"ROBOT_MODE_DISABLED",
			5:	"ROBOT_MODE_ENABLE",
			6:	"ROBOT_MODE_BACKDRIVE",
			7:	"ROBOT_MODE_RUNNING",
			8:	"ROBOT_MODE_RECORDING",
			9:	"ROBOT_MODE_ERROR",
			10:	"ROBOT_MODE_PAUSE",
			11:	"ROBOT_MODE_JOG"
		"""
		self.robot_mode = robot_status.robot_status

	#wait until the robot stops moving
	def sync_robot(self):
			if self.robot_mode == 9:
				self.initialize()
			self.sleep(0.5)
			while self.robot_mode !=5:
				if self.robot_mode == 9:
					self.initialize()
					break
				self.rate.sleep()
			self.Move = False				
	
	#determine the current posiiton 
	def getRobotCoordinate(self):
		self.x_r = self.temp_x_r
		self.y_r = self.temp_y_r
		self.z_r = self.temp_z_r
		self.r_r = self.temp_r_r

	#getting the robot xyz position as soon as they are published
	def robotCoordinate_callback(self, coordinate):
		self.temp_x_r = coordinate.x
		self.temp_y_r = coordinate.y
		self.temp_z_r = coordinate.z
		self.temp_r_r = coordinate.r

	# move the arm based on cmd_vel
	def twist_callback(self, msg):
		x = self.temp_x_r + msg.linear.x
		y = self.temp_y_r + msg.linear.y
		z = self.temp_z_r + msg.linear.z
		r = self.r_coordinate
		if not self.Move:
			self.Move =True
			self.arm_move(x, y, z, r)
			self.sync_robot()

	#decided the angle and distance coefcient
	def get_coefficients(self, angle):
		dist_coef, angle_coef =1,0.1
		if angle <40 and angle >0:
			dist_coef = -0.00420*abs(angle) + 1.01260
			angle_coef = -0.008857* abs(angle) +0.87428
		elif angle >=40:
			pass
		elif angle <=-3 and angle >-10:
			dist_coef = -0.0016*abs(angle) + 0.9508
			angle_coef = 0.0375* abs(angle) + 0.2125
		elif angle <=-10 and angle >-25:
			dist_coef = -0.00184*abs(angle) + 0.96557
			angle_coef = -0.00046* abs(angle) + 0.57276
		elif angle <=-25 and angle >= -35:
			#need to calibrate more
			dist_coef = -0.0016*abs(angle) + 0.9508
			angle_coef = 0.00239* abs(angle) + 0.43692
		elif angle <-35 and angle>-40:
			# a little bit off
			dist_coef = -0.00676*abs(angle) + 1.1133
			# angle_coef = -0.00981*abs(angle) + 0.79615
			angle_coef = 0.0159125*abs(angle) -0.081025
		elif angle <= -40:
			#maybe okay...
			dist_coef = -0.004*abs(angle) + 1.022
			angle_coef = 0.00115*abs(angle) + 0.42455
		return dist_coef, angle_coef


	#if calibration command is on
	def calib_arm_command(self, msg):
		if msg.t =="L":
			self.getRobotCoordinate()
			self.pre_x_r=self.x_r
			self.pre_y_r=self.y_r
			self.pre_z_r=self.z_r
		elif msg.t =="R":
			self.x_i = msg.x
			self.y_i = msg.y
			self.z_i = msg.z
			self.addCoordinate()
		elif msg.t =="M":
			self.calibration()


	#the first move based on the realsense
	def L_move(self,msg):
		if self.robot_mode == 9:
			self.initialize()
		msgs = [msg.x, msg.y, msg.z]  
		self.x_a, self.y_a =0,0
		self.x_a = msg.x*self.x_r_coefficient[0] + self.x_r_intercept
		self.y_a = msg.y*self.y_r_coefficient[0] + self.y_r_intercept
		self.z_a = msg.z*self.z_r_coefficient + self.z_r_intercept
		self.d_from_realsnese = msg.z
		self.x_from_realsnese = msg.x
		_coef =0.7
		self.arm_move(self.x_a*_coef,self.y_a, self.z_a-self.first_height, self.r_coordinate-msg.r)
		
		self.sync_robot()
		self.mg400_dsth.publish(False)

	#after the arm reached the first position
	def D_move(self, msg):
		# added by the angle
		self.getRobotCoordinate()
		self.angle = msg.r * self.coeficient
		self.r_coordinate -= self.angle 
		d = self.distance/math.cos(math.radians(self.angle/self.coeficient))
		_y = d * math.sin(math.radians(self.angle/self.coeficient))
		if self.angle <-3:
			_y *=1.08
		_x = self.distance -  self.distance * math.cos(math.radians(self.angle/self.coeficient))
		self.arm_move(self.x_r+_x, self.y_r + _y, self.z_r, self.r_coordinate)

	#adujst the angle move
	def A_move(self, msg):
		self.getRobotCoordinate()
		self.angle += msg.r * self.coeficient
		self.r_coordinate -= msg.r * self.coeficient
		self.arm_move(self.x_r, self.y_r, self.z_r, self.r_coordinate)

	#Initialize_move
	def I_move(self,msg):
		self.initValue()
		self.arm_enable()
		self.sleep(2)
		self.getRobotCoordinate()
		if msg.z == 10:
			#rotate the endeffector to remove itself from the outlet
			_ex = 90
			if self.r_r >150:
				_ex *=-1
			#reset behavior
			print("z:", msg.z)
			self.arm_move(self.x_r- 40, self.y_r-_ex, self.z_r, self.r_r+_ex)
			self.sync_robot()
		else:
			self.arm_move(300, 0, 60, self.r_coordinate)
			self.sync_robot()
		self.arm_move(self.place_x ,self.place_y,60, self.r_coordinate)
		self.sync_robot()

		#start detecting (this is for experiment)
		if msg.z != 10:
			self.detect_start()


	#final move	
	def F_move(self, msg):
		self.insert_now()
		self.getRobotCoordinate()
		self.arm_move(self.x_r,self.y_r, self.z_r+self.f_height, self.r_coordinate)
		self.sync_robot()
		self.getRobotCoordinate()
			#115 is the dinstance from the camera to the object

		d = self.distance/math.cos(math.radians(self.angle/self.coeficient))
		dis_coef, angle_coef = self.get_coefficients(self.angle/self.coeficient)
		if self.angle/self.coeficient >0 or self.angle/self.coeficient <-10:
			_y = d* math.sin(math.radians(self.angle/self.coeficient))*angle_coef		
		else:
			_y=0
		_y = d* math.sin(math.radians(self.angle/self.coeficient))*angle_coef	
		_x = d* math.cos(math.radians(self.angle/self.coeficient))*dis_coef
		print("d: ", d)
		print("d*sinx",d* math.sin(math.radians(self.angle/self.coeficient)))
		print("dist_coef", dis_coef)
		print("angle_coef", angle_coef)
		# self.distance *= 0.85
		# _y = angle_coef
	
		print("y_adjustment",_y)
		print("angle", self.angle/self.coeficient)
		if self.x_r+_x <450:
			#for experiment
			self.arm_move(self.x_r+_x,self.y_r-_y, self.z_r, self.r_coordinate)
			b_x = self.x_r+_x
			pass
		else:
			print("out of range")
			self.arm_reset()

		self.sync_robot()
		self.getRobotCoordinate()
		b_r = self.r_r
		b_y = self.y_r
		self.arm_disable()
		self.sleep(2)
		# print("battery: ", self.battery)
		# print("battery_criteria", self.battery_criteria)
		_result =0
		if self.insert_result:
			_result=1
			self.insert_result_srvp_(1) #succeeded 
		else:
			self.initValue()
			self.arm_enable()
			self.sleep(2)
			self.arm_move(300, 0, 60, self.r_coordinate)
			self.sync_robot()
			self.arm_move(self.place_x ,self.place_y,60, self.r_coordinate)
			self.sync_robot()
			self.insert_result_srvp_(2) #Failed
			
		# datetime object containing current date and time
		now = datetime.now()
		# dd/mm/YY H:M:S
		dt_string = now.strftime("%Y/%m/%d-%H:%M:%S")	
		with open(self.result_file,"a+") as f:
			f.write(str(dt_string)+' ')
			f.write("大島 ")
			f.write(str(self.angle/self.coeficient) +' ')
			f.write(str(self.d_from_realsnese) +' ')
			f.write(str(self.x_from_realsnese) +' ')
			f.write(str(_result)+'\n')



# chunk of commands
	def execute_arm_commnd(self, msg):
		if msg.t =="L":
			self.L_move(msg)
		elif msg.t == "D":
			self.D_move(msg)
		elif msg.t == "A":
			self.A_move(msg)
		elif msg.t == "I":
			self.I_move(msg)
		elif msg.t =="R":
			self.xy_calib=True
		elif msg.t =="M":
			self.z_calib=True
		elif msg.t =="F":
			self.F_move(msg)
		else:
			pass

	def arm_command(self, msg):
		if self.xy_calib or self.z_calib:
			self.calib_arm_command(msg)
		else:
			self.execute_arm_commnd(msg)


	def battery_callback(self, msg):
		self.battery = msg.battery_voltage

	def insert_now(self):
		self.battery_criteria = self.battery

	def image_callback(self, msg):
		#initial postion for MG400 in image coordinate is 566(x),145(y) and robot coordination is (300, 0)
		#from left to center, (332,145) and robot (300, 113)
		print("the message is ", msg.t)
		"""
		robot_x -> camera_z
		robot_y -> camera_x
		robot_z -> camera_y 
		"""
		temp = msg.y
		msg.y = msg.x
		msg.x = msg.z
		msg.z = temp
		self.arm_command(msg)

		self.last_clb_time_ = rospy.get_time()

	def cancelAppend(self):
		print("cancel")


	def addCoordinate(self):
		if self.x_r != 0  and self.y_r !=0 and self.z_r !=0:
			# pose =np.array([[self.x_i, self.y_i, self.z_i]])
			pose_x = np.array([[self.x_i]])
			pose_y = np.array([[self.y_i]])
			pose_z = np.array([[self.z_i]])
			# z_coordiante = np.array([self.y_i])
			if self.camera_coordinate_x.size == 0:
				self.camera_coordinate_x = pose_x
				self.camera_coordinate_y = pose_y
				self.camera_coordinate_z = pose_z
				# self.camera_coordinate = pose
				# self.camera_z = z_coordiante
			else:
				self.camera_coordinate_x = np.append(self.camera_coordinate_x, pose_x, axis=0)
				self.camera_coordinate_y = np.append(self.camera_coordinate_y, pose_y, axis=0)
				self.camera_coordinate_z = np.append(self.camera_coordinate_z, pose_z, axis=0)
				# self.camera_z = np.append(self.camera_z, z_coordiante)
			self.x_r_arr.append(self.x_r)
			self.y_r_arr.append(self.y_r)
			self.z_r_arr.append(self.z_r)
		else:
			pass
		
	def calibration(self):
		self.camera_z = self.camera_z.reshape(-1,1)
		print(self.camera_z)
		# self.x_coefficient = LinearRegression().fit(self.camera_coordinate, self.x_r_arr)
		# self.y_coefficient = LinearRegression().fit(self.camera_coordinate, self.y_r_arr)
		# self.z_coefficient = LinearRegression().fit(self.camera_z, self.z_r_arr)
		self.x_coefficient = LinearRegression().fit(self.camera_coordinate_x, self.x_r_arr)
		self.y_coefficient = LinearRegression().fit(self.camera_coordinate_y, self.y_r_arr)
		self.z_coefficient = LinearRegression().fit(self.camera_coordinate_z, self.z_r_arr)
		# self.z_coefficient = LinearRegression().fit(self.camera_z, self.z_r_arr)
		print(self.x_coefficient.coef_, self.x_coefficient.intercept_ , self.y_coefficient.coef_, self.y_coefficient.intercept_, self.z_coefficient.coef_, self.z_coefficient.intercept_)
		if self.xy_calib:
			with open(self.xy_filepath,"w+") as file:
				for i in range(len(self.x_coefficient.coef_)):
					file.write(str(self.x_coefficient.coef_[i])+',')
				file.write(str(self.x_coefficient.intercept_)+'\n')
				for i in range(len(self.y_coefficient.coef_)):
					file.write(str(self.y_coefficient.coef_[i])+',')
				file.write(str(self.y_coefficient.intercept_)+'\n')
			with open(self.z_filepath,"w+") as file:
				file.write(str(self.z_coefficient.coef_[0])+',')
				file.write(str(self.z_coefficient.intercept_))
			self.xy_calib_stop_service(Empty)
		elif self.z_calib:
			with open(self.z_filepath,"w+") as file:
				file.write(str(self.z_coefficient.coef_[0])+',')
				file.write(str(self.z_coefficient.intercept_))	
			self.z_calib_stop_service(Empty)	
		self.readCalibFile()

		self.camera_coordinate_x =np.array([[]])
		self.camera_coordinate_y =np.array([[]])
		self.camera_coordinate_z =np.array([[]])
		self.camera_z = np.array([[]])
		self.x_r_arr =[]
		self.y_r_arr =[]
		self.z_r_arr =[]

		

	def work_start_service(self,req):
		print("start movement ")
		self.RUN = 1
		self.arm_enable()
		self.pos_x =300
		first_move = self.arm_move(self.pos_x, self.r_coordinate)
		self.sleep(1)
		self.last_clb_time_ = rospy.get_time()
		return EmptyResponse()


	def work_stop_service(self,req):
		print("stop movement")
		self.RUN = 0
		self.arm_disable()
		return EmptyResponse()
	
	def xy_calib_start_service(self,req):
		print("start xy_alibration")
		self.xy_calib = True
		return EmptyResponse()
	
	def xy_calib_stop_service(self,req):
		print("stop xy_calibration")
		self.xy_calib = False
		self.camera_coordinate_x =np.array([[]])
		self.camera_coordinate_y =np.array([[]])
		self.camera_coordinate_z =np.array([[]])
		self.x_r_arr =[]
		self.y_r_arr =[]
		return EmptyResponse()
	
	def z_calib_start_service(self,req):
		print("start z_calibration")
		self.z_calib = True
		return EmptyResponse()
	
	def z_calib_stop_service(self,req):
		print("stop z_calibration")
		self.z_calib = False
		self.camera_coordinate_x =np.array([[]])
		self.camera_coordinate_y =np.array([[]])
		self.camera_coordinate_z =np.array([[]])
		self.z_r_arr =[]
		return EmptyResponse()


if __name__ == "__main__":
	print("MG400_work start")
	rospy.init_node('MG400_work')
	mv = MOVE()
	rospy.spin()
# 	mv.work_stop_service(Empty)

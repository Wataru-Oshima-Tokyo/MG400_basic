#include <vector>
#include <map>
#include <bringup/robot.h>
#include <bringup/commander.h>
#include <ros/ros.h>
// #include <camera_pkg/Coordinate.h>
#include <geometry_msgs/Twist.h>
#include "roscpp_tutorials/TwoInts.h"
using namespace std;
class RobotMove{

public:

    ros::Publisher pub;
    ros::Subscriber sub;
    ros::NodeHandle nh;
    ros::ServiceServer start, stop;
    ros::ServiceServer arm_enable, arm_disable, arm_move;
    bool getRun();
    void TwistCallBack(const geometry_msgs::Twist& msg);
    virtual bool image_start_service(roscpp_tutorials::TwoInts::Request& req,roscpp_tutorials::TwoInts::Response& res);
    virtual bool image_stop_service(roscpp_tutorials::TwoInts::Request& req, roscpp_tutorials::TwoInts::Response& res);
    
    //topics 
    const std::string SERVICE_START = "/mg_work/start";
    const std::string SERVICE_STOP = "/mg_work/stop";
    RobotMove();
    ~RobotMove();
    // static void callback(const geometry_msgs::Twist& msg) { // because the mouse call back cannot accept non-static func
    //     CAMERA_CV *foo = (CAMERA_CV*)userdata; // cast user data back to "this"
    //     foo->TwistCallBack();
    // }
private:
    bool RUN = false;

};


 
 bool RobotMove::image_start_service(roscpp_tutorials::TwoInts::Request& req,roscpp_tutorials::TwoInts::Response& res){
   cout << "robot start" << endl;
//    CR5 en(nh, "enable");
//    bringup::EnableRobot::Request _req;
//    bringup::EnableRobot::Response _res;
//    en.enableRobot(_req,_res);
  //  CR5Commander mg("192.168.1.6");
   RUN = true;
   return RUN;

 }

 bool RobotMove::image_stop_service(roscpp_tutorials::TwoInts::Request& req,roscpp_tutorials::TwoInts::Response& res){
   cout << "robot stop" << endl;
   RUN = false;
   
//    bringup::EnableRobot::Request _req;
//    bringup::EnableRobot::Response _res;
//    dn(_req,_res);
   return RUN;
 }

bool RobotMove::getRun(){
  return RUN;
}

RobotMove::RobotMove(){

};
RobotMove::~RobotMove(){};

void RobotMove::TwistCallBack(const geometry_msgs::Twist& msg){
    ROS_INFO_STREAM("Subscriber velocities:"<<" linear="<<msg.linear.x<<" angular="<<msg.angular.z);

}

int main(int argc, char** argv){
    ros::init(argc, argv, "mg_work_start");
    RobotMove rm;
    // bringup::MG400Robot bu;
    ros::Rate loop_rate(100);
    bringup::EnableRobot en;
    // bringup::DisableRobot dn;
    rm.sub = rm.nh.subscribe("cmd_vel",1000,&RobotMove::TwistCallBack, &rm);
    rm.start = rm.nh.advertiseService(rm.SERVICE_START, &RobotMove::clbk_start_service, &rm);
    rm.stop = rm.nh.advertiseService(rm.SERVICE_STOP, &RobotMove::clbk_stop_service, &rm);
    // rm.arm_enable = rm.nh.advertiseService(rm.SERVICE_STOP, &bringup::EnableRobot::enableRobot, &en);
    // rm.arm_enable = rm.nh.advertiseService('/bringup/srv/EnableRobot',&MG400Robot::enableRobot, &robot);
    while(ros::ok()){
        
        loop_rate.sleep();
        ros::spinOnce();
    }

    
    return 0;
}

'''*-----------------------------------------------------------------------*---
                                                         Author: Jason Ma
                                                         Date  : Jul 17 2016
   File Name  : statusmon.py
   Description: Displays data from buffers that Cubeception 3 writes to.
                The monitor includes a polar graph for targets, orientation 
                viewer, thruster heatmap, location/velocity/acceleration plots,
                and buffer status messages. 
---*-----------------------------------------------------------------------*'''
import sys
sys.path.insert(0, '../DistributedSharedMemory/build')
sys.path.insert(0, '../PythonSharedBuffers/src')
from Constants import *
import pydsm

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.animation as animation
from mpl_toolkits.mplot3d import Axes3D

from ctypes import *
from Sensor import *
from Master import *
from Navigation import *
from Vision import *
from Serialization import *

from itertools import product, combinations
import numpy as np
from numpy import sin, cos

'''[RUN VARS]---------------------------------------------------------------'''
#DSM Constants
CLIENT_SERV  = SONAR_SERVER_ID #Server id to connect to
CLIENT_ID    = 60              #Client id to register to server
NUM_BUFFERS  = 12              #Number of buffers to read from

#Display Constants
NUM_PL_LINES = 36   #Number of polar theta lines to plot
NUM_TARGETS  = 2    #Number of targets to plot on polar targets viewer
CUBE_POINTS  = 16   #Number of points in cube orientation plot
ARROW_POINTS = 8    #Number of points in cube arrow plot
NUM_MV_LINES = 11   #Number o movement lines to plot
HIST_LENGTH  = 50   #Number of past data points to store for movement viewer
DELAY        = 1000 #Millisecond delay between drawings
bufNames = [MOTOR_KILL,             MOTOR_HEALTH,              MOTOR_OUTPUTS,
            SENSORS_LINEAR,         SENSORS_ANGULAR,           SENSORS_DATA, 
            MASTER_CONTROL,         MASTER_GOALS,              MASTER_SENSOR_RESET,
            TARGET_LOCATION,        TARGET_LOCATION,           TARGET_LOCATION]
bufIps = [MOTOR_SERVER_IP,          MOTOR_SERVER_IP,           MOTOR_SERVER_IP,
          SENSOR_SERVER_IP,         SENSOR_SERVER_IP,          SENSOR_SERVER_IP, 
          MASTER_SERVER_IP,         MASTER_SERVER_IP,          MASTER_SERVER_IP, 
          FORWARD_VISION_SERVER_IP, DOWNWARD_VISION_SERVER_IP, SONAR_SERVER_IP]
bufIds = [MOTOR_SERVER_ID,          MOTOR_SERVER_ID,           MOTOR_SERVER_ID,
          SENSOR_SERVER_ID,         SENSOR_SERVER_ID,          SENSOR_SERVER_ID, 
          MASTER_SERVER_ID,         MASTER_SERVER_ID,          MASTER_SERVER_ID, 
          FORWARD_VISION_SERVER_ID, DOWNWARD_VISION_SERVER_ID, SONAR_SERVER_ID]

FIG_WIDTH    = 16                             #Aspect width
FIG_HEIGHT   = 8                              #Aspect height
FIG_NAME     = 'Cubeception 3 Status Monitor' #Name displayed in window
PLOT_STYLE   = 'dark_background'              #Background style
LIGHT_GREEN  = (0, 1, 0, 1)                   #RGBA color
DARK_GREEN   = (0, 0.5, 0, 1)                 #RGBA color
LIGHT_RED    = (1, 0.75, 0.75, 1)             #RGBA color
DARK_RED     = (1, 0, 0, 1)                   #RGBA color
LIGHT_YELLOW = (1, 1, 0, 1)                   #RGBA color
DPI_DISPLAY  = 100                            #Dots per inch of display
FONT_SIZE    = 8                              #Default text font size
TITLE_SIZE   = 10                             #Default title font size

'''Init------------------------------------------------------------------------
Generates figure and subplots, sets base layout and initializes data
----------------------------------------------------------------------------'''

'''[Connect to DSM Server]--------------------------------------------------'''
#Initialize client
client = pydsm.Client(CLIENT_SERV, CLIENT_ID, True)

#Initialize remote buffers
for i in range(NUM_BUFFERS):
  client.registerRemoteBuffer(bufNames[i], bufIps[i], int(bufIds[i]))

'''[Initialize Figure/Subplots]---------------------------------------------'''
#Background style of figure
plt.style.use(PLOT_STYLE)

#Set default matplotlib artist values
mpl.rc(('text', 'xtick', 'ytick'), color = LIGHT_GREEN)
mpl.rc(('lines', 'grid'), color = DARK_GREEN)
mpl.rc('axes', edgecolor = LIGHT_GREEN, titlesize = TITLE_SIZE)
mpl.rc('font', size = FONT_SIZE)
mpl.rc('grid', linestyle = ':')

#Create figure with 16:8 (width:height) ratio
fig = plt.figure(figsize = (FIG_WIDTH, FIG_HEIGHT), dpi = DPI_DISPLAY)
fig.canvas.set_window_title(FIG_NAME)
#fig.suptitle(FIG_NAME)   #Would set name of subplot
  
#Create subplots on a 4 row 8 column grid
ax1 = plt.subplot2grid((6, 12), (0, 0), rowspan = 6, colspan = 6, polar = True)
ax2 = plt.subplot2grid((6, 12), (0, 6), rowspan = 3, colspan = 3, projection = '3d')
ax3 = plt.subplot2grid((6, 12), (0, 9), rowspan = 2, colspan = 3)
ax4 = plt.subplot2grid((6, 12), (3, 6), rowspan = 3, colspan = 3)
ax5 = plt.subplot2grid((6, 12), (2, 9), rowspan = 4, colspan = 3)
plt.tight_layout(pad = 2)

'''[Initialize Data]--------------------------------------------------------'''
#Holds all displayed data from buffers
data = np.zeros((9,4))

'''[Init Polar Targets]-----------------------------------------------------'''
#Default vision display
data[0][0] = 0 #CV forw
data[0][1] = 5
data[0][2] = 4
data[0][3] = 0

data[1][0] = 0 #CV down
data[1][1] = 0
data[1][2] = -6
data[1][3] = 256

#Polar target marks and text
cvfMark, = ax1.plot(0, 0, marker = 'o', c = DARK_RED, markersize = 10)
cvdMark, = ax1.plot(0, 0, marker = 'o', c = DARK_RED, markersize = 10)
cvfText = ax1.text(0, 0, '', bbox = dict(facecolor = DARK_GREEN, alpha = 0.3), color = 'w')
cvdText = ax1.text(0, 0, '', bbox = dict(facecolor = DARK_GREEN, alpha = 0.3), color = 'w')

'''[Init Orientation]-------------------------------------------------------'''
#Cube for orientation viewer
cube = np.zeros((3, CUBE_POINTS))
cube[0] = [-1, -1, -1, 1,  1, -1, -1,  1,  1, -1, -1, -1,  1,  1,  1,  1]
cube[1] = [-1, -1,  1, 1,  1,  1, -1, -1, -1, -1,  1,  1,  1, -1, -1,  1]
cube[2] = [-1,  1,  1, 1, -1, -1, -1, -1,  1,  1,  1, -1, -1, -1,  1,  1]
cubeLines = ax2.plot_wireframe(cube[0], cube[1], cube[2], colors = LIGHT_GREEN)

#Arrow for locating front face of cube
ca = np.zeros((3, ARROW_POINTS))
ca[0] = [0, 2, 1.75,  1.75, 2, 1.75,  1.75, 2]
ca[1] = [0, 0, 0.25, -0.25, 0,    0,     0, 0]
ca[2] = [0, 0,    0,     0, 0, 0.25, -0.25, 0]
cubeArrow = ax2.plot_wireframe(ca[0], ca[1], ca[2], colors = LIGHT_YELLOW)

'''[Init Heatmap]-----------------------------------------------------------'''
#Heatmap
heatmap = ax3.imshow(np.random.uniform(size = (3, 4)), cmap = 'RdBu', interpolation = 'nearest')

'''[Init Movement]----------------------------------------------------------'''
#Past ax4 data to plot
dataHist = np.zeros((NUM_MV_LINES, HIST_LENGTH))

#Random data to initialize with
dataHist[0][49] = 1
dataHist[1][44] = 2
dataHist[2][39] = 4
dataHist[3][34] = 6
dataHist[4][29] = 8
dataHist[5][24] = 10
dataHist[6][19] = 12
dataHist[7][14] = 14
dataHist[8][9] = 16
dataHist[9][4] = 18
dataHist[10][1] = 20

#Colors for ax4 plots
colors = ['#ff0000', '#cf0000', '#8f0000', '#00ff00', '#00cf00', '#008f00',
          '#004f00', '#0000ff', '#0000cf', '#00008f', '#00004f']

#Initialize position graph plots
mLines = [ax4.plot([], '-', color = colors[j])[0] for j in range(NUM_MV_LINES)]

'''[Init Status]------------------------------------------------------------'''
statusStrings = np.empty(NUM_BUFFERS, dtype = 'object')
status = ax5.text(0.05, .65, '')

'''initPlot--------------------------------------------------------------------
Sets up subplots and starting image of figure to display
----------------------------------------------------------------------------'''
def initFigure():

  '''[Polar Targets]--------------------------------------------------------'''
  #Set subplot title
  ax1.set_title('Targets')
  
  #Set label locations appropriately
  ax1.set_theta_zero_location("N")
  ax1.set_theta_direction(-1)
  
  #Format ticks and labels
  ax1.set_thetagrids(np.linspace(0, 360, NUM_PL_LINES, endpoint = False), frac = 1.05)
  ax1.set_rlabel_position(90)

  #Make ygridlines more visible (circular lines)
  for line in ax1.get_ygridlines():
    line.set_color(LIGHT_GREEN)
  
  '''[Orientation]----------------------------------------------------------'''
  #Set subplot title
  ax2.set_title('Orientation')

  #Enable grid
  ax2.grid(b = False)
  
  #Set color of backgrounds
  ax2.w_xaxis.set_pane_color((0, 0.075, 0, 1))
  ax2.w_yaxis.set_pane_color((0, 0.075, 0, 1))
  ax2.w_zaxis.set_pane_color((0, 0.125, 0, 1))

  #Set color of axis lines
  ax2.w_xaxis.line.set_color(LIGHT_GREEN)
  ax2.w_yaxis.line.set_color(LIGHT_GREEN)
  ax2.w_zaxis.line.set_color(LIGHT_GREEN)

  #Set tick lines
  ax2.set_xticks([])
  ax2.set_yticks([])
  ax2.set_zticks([])

  #Set green axis labels
  ax2.set_xlabel('X axis', color = LIGHT_GREEN)
  ax2.set_ylabel('Y axis', color = LIGHT_GREEN)
  ax2.set_zlabel('Z axis', color = LIGHT_GREEN)

  '''[Thruster Heatmap]-----------------------------------------------------'''
  #Set subplot title
  ax3.set_title('Thruster Heatmap')

  #Set ticks to properly extract parts of data
  ax3.set_xticks([0, 1, 2, 3])
  ax3.set_yticks([0, 1, 2])

  #Label ticks so they correspond to motors
  ax3.set_xticklabels(['1', '2', '3', '4'])
  ax3.set_yticklabels(['X', 'Y', 'Z'])
  
  '''[Position/Velocity/Acceleration]---------------------------------------'''
  #Set subplot title
  ax4.set_title('Movement')
  
  #Set x scale
  ax4.set_xticks(np.linspace(0, HIST_LENGTH, NUM_MV_LINES))
  
  #Enable grid
  ax4.grid(True)

  '''[Status]---------------------------------------------------------------'''
  #Set subplot title
  ax5.set_title('Status')

  '''[Multiple Axes]--------------------------------------------------------'''
  for ax in ax2, ax3, ax5:
    ax.tick_params(axis = 'both', which = 'both', bottom = 'off', top = 'off',
           left = 'off', right = 'off')
           
  for ax in ax2, ax5:
    ax.tick_params(labelbottom = 'off', labelleft = 'off')

'''quaternionFuncs-------------------------------------------------------------
Functions to create and use quaternions for robot orientation viewer
----------------------------------------------------------------------------'''
def normalize(v, tolerance = 0.00001):
  magnSqr = sum(n * n for n in v)
  if abs(magnSqr - 1.0) > tolerance:
    magn = pow(magnSqr, 1/2)
    v = tuple(n / magn for n in v)
  return v

def q_mult(q1, q2):
  w1, x1, y1, z1 = q1
  w2, x2, y2, z2 = q2
  w = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
  x = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
  y = w1 * y2 + y1 * w2 + z1 * x2 - x1 * z2
  z = w1 * z2 + z1 * w2 + x1 * y2 - y1 * x2
  return w, x, y, z

def q_conjugate(q):
  w, x, y, z = q
  return (w, -x, -y, -z)

def qv_mult(q1, v1):
  q2 = (0.0,) + v1
  return q_mult(q_mult(q1, q2), q_conjugate(q1))[1:]

def axisangle_to_q(v, theta):
  v = normalize(v)
  x, y, z = v
  theta /= 2
  w = cos(theta)
  x = x * sin(theta)
  y = y * sin(theta)
  z = z * sin(theta)
  return w, x, y, z

def q_to_axisangle(q):
  w, v = q[0], q[1:]
  theta = acos(w) * 2.0
  return normalize(v), theta

'''getBufferData---------------------------------------------------------------
Obtains most recent buffer data
----------------------------------------------------------------------------'''
def getBufferData():
  
  #Check each buffer's status and update data array if active
  for i in range(NUM_BUFFERS):
    temp, active = client.getRemoteBufferContents(bufNames[i], bufIps[i], bufIds[i])
    if active:
      if i == 0:                          #Motor Kill
        temp = Unpack(Kill, temp)
        data[8][0] = temp.isKilled
      elif i == 1:                        #Motor Health
        temp = Unpack(Health, temp)
        data[8][1] = temp.saturated
        data[8][2] = temp.direction
      elif i == 2:                        #Motor Outputs
        temp = Unpack(Outputs, temp)
        for j in range(4):
          data[3][j] = temp.motors[j]
        for j in range(4):
          data[4][j] = temp.motors[j + 4]
      elif i == 3:                        #Sensors Linear
        temp = Unpack(Linear, temp)
        for j in range(3):
          data[5][j] = temp.pos[j]
          data[6][j] = temp.vel[j]
          data[7][j] = temp.acc[j]
      elif i == 4:                        #Sensors Angular
        temp = Unpack(Angular, temp)
        for j in range(4):
          data[2][j] = temp.pos[j]
      #elif i == 5:                       #Sensors Data
      #elif i == 6:                       #Master Control 
      #elif i == 7:                       #Master Goals
      #elif i == 8:                       #Master Sensor Reset
      elif i == 9:                        #CV Forw Target Location
        temp = Unpack(Location, temp)
        data[0][0] = temp.x
        data[0][1] = temp.y
        data[0][2] = temp.z
        data[0][3] = temp.confidence
      elif i == 10:                       #CV Down Target Location
        temp = Unpack(Location, temp)
        data[1][0] = temp.x
        data[1][1] = temp.y
        data[1][2] = temp.z
        data[1][3] = temp.confidence
      #elif i == 11:                      #Sonar Target Location

      #Set status string to indicate whether buffer is up or down
      statusStrings[i] = 'Up  '
    else:
      statusStrings[i] = 'Down'
  
'''animate---------------------------------------------------------------------
Updates subplots of figure
----------------------------------------------------------------------------'''
def animate(i):
  
  global ax1, ax2, ax3, ax4, ax5, data, dataHist, cubeLines, cubeArrow

  #Grab latest data to plot as well as info on whether buffers are online
  getBufferData()
  
  '''[Polar Targets]--------------------------------------------------------'''  
  #Determine max for scale adjustments
  if data[0][1] > data[1][1]:
    max = data[0][1]
  else:
    max = data[1][1]

  #Adjust scale of ax1 to fit data nicely
  ax1.set_yticks(np.linspace(0, max * 6 / 5, 7))

  #Ensure statusmon doesn't crash if CV returns crazy values
  if data[0][2] > 0:
    data[0][2] = 0
  elif data[0][2] < -10:
    data[0][2] = -10

  if data[1][2] > 10:
    data[1][2] = 10
  elif data[1][2] < -10:
    data[1][2] = -10

  if data[0][3] < 0:
    data[0][3] = 0
  elif data[0][3] > 255:
    data[0][3] = 255

  if data[1][3] < 0:
    data[1][3] = 0
  elif data[1][3] > 255:
    data[1][3] = 255

  #Update CV forward data
  cvfMark.set_data(data[0][0], data[0][1])
  cvfMark.set_color((1, data[0][2] / -10, 0, 1))
  cvfMark.set_markersize(20 - data[0][3] * 5 / 128)

  #Update CV down data
  cvdMark.set_data(data[1][0], data[1][1])
  cvdMark.set_color((1, data[1][2] / -20 + 0.5, 0, 1))
  cvdMark.set_markersize(20 - data[1][3] * 5 / 128)

  #Update CV forward text
  cvfText.set_position((data[0][0], data[0][1]))  
  cvfText.set_text('CVForw\nx:{0:5.3f}\ny:{1:5.3f}\nz:{2:5.3f}\nc:{3}'.format(
                             data[0][0], data[0][1], data[0][2], data[0][3]))

  #Update CV down text
  cvdText.set_position((data[1][0], data[1][1]))  
  cvdText.set_text('CVDown\nx:{0:5.3f}\ny:{1:5.3f}\nz:{2:5.3f}\nc:{3}'.format(
                             data[1][0], data[1][1], data[1][2], data[1][3]))

  '''[Orientation]----------------------------------------------------------'''
  #Only rotate model if stream is online
  if statusStrings[4] == 'Up  ':
    quat = (data[2][0], data[2][1], data[2][2], data[2][3])
  else:
    #Default quaternion results in no rotation
    quat = (1, 0, 0, 0)
   
  #Reset orientation of cube and arrow
  cube[0] = [-1, -1, -1, 1,  1, -1, -1,  1,  1, -1, -1, -1,  1,  1,  1,  1]
  cube[1] = [-1, -1,  1, 1,  1,  1, -1, -1, -1, -1,  1,  1,  1, -1, -1,  1]
  cube[2] = [-1,  1,  1, 1, -1, -1, -1, -1,  1,  1,  1, -1, -1, -1,  1,  1]

  ca[0] = [0, 2, 1.75,  1.75, 2, 1.75,  1.75, 2]
  ca[1] = [0, 0, 0.25, -0.25, 0,    0,     0, 0]
  ca[2] = [0, 0,    0,     0, 0, 0.25, -0.25, 0]
  
  #Apply transformation to all points of cube
  for j in range(16):
    v = qv_mult(quat, (cube[0][j], cube[1][j], cube[2][j]))
    cube[0][j] = v[0]
    cube[1][j] = v[1]
    cube[2][j] = v[2]
  
  #Apply transformation to all points of front facing arrow
  for j in range(8):
    v = qv_mult(quat, (ca[0][j], ca[1][j], ca[2][j]))
    ca[0][j] = v[0]
    ca[1][j] = v[1]
    ca[2][j] = v[2]
  
  #Remove old wireframes and plot new ones
  cubeLines.remove()
  cubeArrow.remove()  
  cubeLines = ax2.plot_wireframe(cube[0], cube[1], cube[2], colors = LIGHT_GREEN)
  cubeArrow = ax2.plot_wireframe(ca[0], ca[1], ca[2], colors = LIGHT_YELLOW)
  
  '''[Thruster Heatmap]-----------------------------------------------------'''
  #Map data to heatmap
  heatArray = [[data[4][0], data[4][1], 0, 0], [data[4][2], data[4][3], 0, 0], 
              [data[3][0], data[3][1], data[3][2], data[3][3]]]
  
  #Update motor heatmap
  heatmap.set_array(heatArray)

  '''[Movement]-------------------------------------------------------------'''
  #Update data for ax4 plots
  moveX = np.linspace(0, HIST_LENGTH - 1, HIST_LENGTH)

  #Transfer data into data history
  for j in range(NUM_MV_LINES):
    for k in range(HIST_LENGTH - 1):
      dataHist[j][k] = dataHist[j][k + 1]
  for j in range(3):
    dataHist[j][HIST_LENGTH - 1] = data[5][j]
  for j in range(3):
    dataHist[j + 3][HIST_LENGTH - 1] = data[6][j]
  for j in range(3):
    dataHist[j + 7][HIST_LENGTH - 1] = data[7][j]

  #Calculate total velocity/acceleration
  dataHist[6][HIST_LENGTH - 1] = pow(pow(data[6][0], 2) + pow(data[6][1], 2) + pow(data[6][2], 2), 1/2)
  dataHist[10][HIST_LENGTH - 1] = pow(pow(data[7][0], 2) + pow(data[7][1], 2) + pow(data[7][2], 2), 1/2)

  #Update data for each plot
  for j in range(NUM_MV_LINES):
    mLines[j].set_data(moveX, dataHist[j])
  
  #Determine highest value to scale y axis properly
  ymax = dataHist[0][0]
  ymin = dataHist[0][0]
  for j in range(NUM_MV_LINES):
    for k in range(HIST_LENGTH):
      if dataHist[j][k] > ymax:
        ymax = dataHist[j][k]
      elif dataHist[j][k] < ymin:
        ymin = dataHist[j][k]

  #Scale ax4 plot
  ax4.set_ylim(ymin, ymax + (ymax - ymin) / 5)

  if(ymin != ymax):
    movementTicks = np.linspace(ymin, ymax + (ymax - ymin) / 5, 7)
    ax4.set_yticks(movementTicks)

  #Update legend with latest data values
  ax4.legend(['px:{}'.format(dataHist[0][HIST_LENGTH - 1]),
              'py:{}'.format(dataHist[1][HIST_LENGTH - 1]),
              'py:{}'.format(dataHist[2][HIST_LENGTH - 1]),
              'vx:{}'.format(dataHist[3][HIST_LENGTH - 1]),
              'vy:{}'.format(dataHist[4][HIST_LENGTH - 1]),
              'vz:{}'.format(dataHist[5][HIST_LENGTH - 1]),
              'vt:{}'.format(dataHist[6][HIST_LENGTH - 1]),
              'ax:{}'.format(dataHist[7][HIST_LENGTH - 1]),
              'ay:{}'.format(dataHist[8][HIST_LENGTH - 1]),
              'az:{}'.format(dataHist[9][HIST_LENGTH - 1]),
              'at:{}'.format(dataHist[10][HIST_LENGTH - 1])], 
              loc = 'upper left', numpoints = 1)

  '''[Multiple Axes]--------------------------------------------------------'''
  #Update status text
  status.set_text('Buffer Status:\n' \
         'Motor Kill:{}\nMotor Health:{}\nMotor Outputs:{}\n' \
         'Sensor Lin:{}\nSensor Ang:{}\nSensor Data:{}\n' \
         'Master Control:{}\nMaster Goals:{}\nMaster Sensor Reset:{}\n' \
         'CVDown Target:{}\nCVForw Target:{}\nSonar Target:{}'.format(
            statusStrings[0], statusStrings[1], statusStrings[2], 
            statusStrings[3], statusStrings[4], statusStrings[5],
            statusStrings[6], statusStrings[7], statusStrings[8], 
            statusStrings[9], statusStrings[10], statusStrings[11]))
  
#Set up animation
ani = animation.FuncAnimation(fig, animate, init_func = initFigure, 
                              interval = DELAY)

#Show the figure
plt.show()

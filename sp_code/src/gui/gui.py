#!/usr/bin/env python2



import sys
import shutil
import os.path
import glob
import traceback
import time
import numpy as np
from PyQt4 import uic
from scipy.io import wavfile
from PyQt4.QtCore import *
from PyQt4.QtGui import *
from PyQt4 import QtCore,QtGui

import pyaudio
from utils import read_wav, write_wav, time_str, monophonic
from interface import ModelInterface

FORMAT=pyaudio.paInt16
NPDtype = 'int16'
NAMELIST = ['Nobody']

class RecorderThread(QThread):
    def __init__(self, main):
        QThread.__init__(self)
        self.main = main

    def run(self):
        self.start_time = time.time()
        while True:
            data = self.main.stream.read(1)
            i = ord(data[0]) + 256 * ord(data[1])
            if i > 32768:
                i -= 65536
            stop = self.main.add_record_data(i)
            if stop:
                break

class Main(QMainWindow):
    CONV_INTERVAL = 0.4
    CONV_DURATION = 1.5
    CONV_FILTER_DURATION = CONV_DURATION
    FS = 8000
    TEST_DURATION = 3

    def __init__(self, parent=None):
        QWidget.__init__(self, parent)
        uic.loadUi("edytor.ui", self)
        self.statusBar()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.timer_callback)

        #self.noiseButton.clicked.connect(self.noise_clicked)
        self.recording_noise = False
        #self.loadNoise.clicked.connect(self.load_noise)

        self.enrollRecord.clicked.connect(self.start_enroll_record)
        self.stopEnrollRecord.clicked.connect(self.stop_enroll_record)
        #self.enrollFile.clicked.connect(self.enroll_file)
        self.enroll.clicked.connect(self.do_enroll)
        self.startTrain.clicked.connect(self.start_train)
        #self.dumpBtn.clicked.connect(self.dump)
        #self.loadBtn.clicked.connect(self.load)

        self.recoRecord.clicked.connect(self.start_reco_record)
        self.stopRecoRecord.clicked.connect(self.stop_reco_record)
#        self.newReco.clicked.connect(self.new_reco)
        #self.recoFile.clicked.connect(self.reco_file)
        #self.recoInputFiles.clicked.connect(self.reco_files)

        #UI.init
        self.userdata =[]
       
        self.Userchooser.currentIndexChanged.connect(self.showUserInfo)
        self.ClearInfo.clicked.connect(self.clearUserInfo)
        self.UpdateInfo.clicked.connect(self.updateUserInfo)
        self.UploadImage.clicked.connect(self.upload_avatar)
	
	

        #movie test
        self.movie = QMovie(u"image/recording.gif")
        self.movie.start()
        self.movie.stop()
        self.Animation.setMovie(self.movie)
        self.Animation_2.setMovie(self.movie)
        #self.Animation_3.setMovie(self.movie)

        #self.aladingpic = QPixmap(u"image/a_hello.png")
        #self.Alading.setPixmap(self.aladingpic)
        #self.Alading_conv.setPixmap(self.aladingpic)

        #default user image setting
        self.avatarname = "image/nouser.jpg"
        self.defaultimage = QPixmap(self.avatarname)
        self.Userimage.setPixmap(self.defaultimage)
        self.recoUserImage.setPixmap(self.defaultimage)
        #self.convUserImage.setPixmap(self.defaultimage)
        self.load_avatar('avatar/')

      # Graph Window init
        #self.graphwindow = GraphWindow()
        self.newname = ""
        self.lastname = ""
        #self.Graph_button.clicked.connect(self.graphwindow.show)
        #self.convRecord.clicked.connect(self.start_conv_record)
        #self.convStop.clicked.connect(self.stop_conv)

        self.backend = ModelInterface()

        #init
        try:
	    self.loadUsers() 	
            fs, signal = read_wav("bg.wav")
            self.backend.init_noise(fs, signal)
        except:
            pass




    ############ RECORD
    def start_record(self):
        self.pyaudio = pyaudio.PyAudio()
        self.status("Recording...")
        self.movie.start()
        self.Alading.setPixmap(QPixmap(u"image/a_thinking.png"))


        self.recordData = []
        self.stream = self.pyaudio.open(format=FORMAT, channels=1, rate=Main.FS,
                        input=True, frames_per_buffer=1)
        self.stopped = False
        self.reco_th = RecorderThread(self)
        self.reco_th.start()

        self.timer.start(1000)
        self.record_time = 0
        self.update_all_timer()

    def add_record_data(self, i):
        self.recordData.append(i)
        return self.stopped

    def timer_callback(self):
        self.record_time += 1
        self.status("Recording..." + time_str(self.record_time))
        self.update_all_timer()

    def stop_record(self):
        self.movie.stop()
        self.stopped = True
        self.reco_th.wait()
        self.timer.stop()
        self.stream.stop_stream()
        self.stream.close()
        self.pyaudio.terminate()
        self.status("Record stopeed")

  


    ###### RECOGNIZE
    def start_reco_record(self):
        self.Alading.setPixmap(QPixmap(u"image/a_hello"))
        self.recoRecordData = np.array((), dtype=NPDtype)
        self.start_record()

    def stop_reco_record(self):
        self.stop_record()
        signal = np.array(self.recordData, dtype=NPDtype)
        self.reco_remove_update(Main.FS, signal)

    def reco_do_predict(self, fs, signal):
        label = self.backend.predict(fs, signal)
        if not label:
            label = "Nobody"
        print label
        self.recoUsername.setText(label)
        self.Alading.setPixmap(QPixmap(u"image/a_result.png"))
        self.recoUserImage.setPixmap(self.get_avatar(label))

        # TODO To Delete
        write_wav('reco.wav', fs, signal)

    def reco_remove_update(self, fs, signal):
        new_signal = self.backend.filter(fs, signal)
        print "After removed: {0} -> {1}".format(len(signal), len(new_signal))
        self.recoRecordData = np.concatenate((self.recoRecordData, new_signal))
        real_len = float(len(self.recoRecordData)) / Main.FS / Main.TEST_DURATION * 100
        if real_len > 100:
            real_len = 100

        self.reco_do_predict(fs, self.recoRecordData)


   

    ########## ENROLL
    def start_enroll_record(self):
        self.enrollWav = None
        self.start_record()

    def stop_enroll_record(self):
        self.stop_record()
        print self.recordData[:300]
        signal = np.array(self.recordData, dtype=NPDtype)
        self.enrollWav = (Main.FS, signal)

        # TODO To Delete
        write_wav('enroll.wav', *self.enrollWav)

    def do_enroll(self):
        name = self.Username.text().trimmed()
        if not name:
            self.warn("Please Input Your Name")
            return
	#if (self.Userchooser.currentIndex()-1) ==0:
	self.addUserInfo()
        new_signal = self.backend.filter(*self.enrollWav)
        print "After removed: {0} -> {1}".format(len(self.enrollWav[1]), len(new_signal))
        print "Enroll: {:.4f} seconds".format(float(len(new_signal)) / Main.FS)
        if len(new_signal) == 0:
            print "Error! Input is silent! Please enroll again"
            return
        self.backend.enroll(name, Main.FS, new_signal)
	#self.start_train()
	self.dump()
	#self.load()
	#self.start_train()
	
	

    def start_train(self):
        self.status("Training...")
        self.backend.train()
        self.status("Training Done.")

    ####### UI related
   
    def loadUsers(self):
        with open("avatar/metainfo.txt") as db:
            for line in db:
                tmp = line.split('|')
                self.userdata.append(tmp)
                self.Userchooser.addItem(tmp[0])
	self.load()
	#self.start_train()

    def upload_avatar(self):
        fname = QFileDialog.getOpenFileName(self, "Open JPG File", "", "File (*.jpg)")
        if not fname:
            return
        self.avatarname = fname
        self.Userimage.setPixmap(QPixmap(fname))

    def showUserInfo(self):
        for user in self.userdata:
            if self.userdata.index(user) == self.Userchooser.currentIndex() - 1:
                self.Username.setText(user[0])
                self.Userage.setValue(int(user[1]))
                if user[2] == 'F':
                    self.Usersex.setCurrentIndex(1)
                else:
                    self.Usersex.setCurrentIndex(0)
		self.Password.setText(user[3])
                self.Userimage.setPixmap(self.get_avatar(user[0]))

    def updateUserInfo(self):
        userindex = self.Userchooser.currentIndex() - 1
        u = self.userdata[userindex]
        u[0] = unicode(self.Username.displayText())
        u[1] = self.Userage.value()
        if self.Usersex.currentIndex():
            u[2] = 'F'
        else:
            u[2] = 'M'
 	u[3] = self.Password.displayText()
        with open("avatar/metainfo.txt","w") as db:
            for user in self.userdata:
                for i in range(4):
                    db.write(str(user[i]) + "|")
                db.write("\n")


    def writeuserdata(self):
	print "Witing User Info to File"
        with open("avatar/metainfo.txt","w") as db:
            for user in self.userdata:
                for i in range (4):
		    print "Current Value {0}",str(user[i])	
                    db.write(str(user[i]) + "|")
                db.write("\n")

    def clearUserInfo(self):
        self.Username.setText("")
        self.Password.setText("")
        self.Userage.setValue(0)
        self.Usersex.setCurrentIndex(0)
        self.Userimage.setPixmap(self.defaultimage)

    def addUserInfo(self):
	print("Witing User Info")
        for user in self.userdata:
            if user[0] == unicode(self.Username.displayText()):
                return
        newuser = []
        newuser.append(unicode(self.Username.displayText()))
        newuser.append(self.Userage.value())
        if self.Usersex.currentIndex():
            newuser.append('F')
        else:
            newuser.append('M')
	newuser.append(self.Password.displayText())
        #if self.avatarname:
            #shutil.copy(self.avatarname, 'avatar/' + user[0] + '.jpg')
        self.userdata.append(newuser)
        self.writeuserdata()
        self.Userchooser.addItem(unicode(self.Username.displayText()))


    ############# UTILS
    def warn(self, s):
        QMessageBox.warning(self, "Warning", s)

    def status(self, s=""):
        self.statusBar().showMessage(s)

    def update_all_timer(self):
        s = time_str(self.record_time)
        self.enrollTime.setText(s)
        self.recoTime.setText(s)
        

    def dump(self):
        fname = "model/tranning.txt"
        if fname:
            try:
                self.backend.dump(fname)
            except Exception as e:
                self.warn(str(e))
            else:
                self.status("Dumped to file: " + fname)

    def load(self):
        fname = "model/tranning.txt"
        if fname:
            try:
                self.backend = ModelInterface.load(fname)
            except Exception as e:
                self.warn(str(e))
            else:
                self.status("Loaded from file: " + fname)
   

    def load_avatar(self, dirname):
        self.avatars = {}
        for f in glob.glob(dirname + '/*.jpg'):
            name = os.path.basename(f).split('.')[0]
            print f, name
            self.avatars[name] = QPixmap(f)

    def get_avatar(self, username):
        p = self.avatars.get(str(username), None)
        if p:
            return p
        else:
            return self.defaultimage

    def printDebug(self):
        for name, feat in self.backend.features.iteritems():
            print name, len(feat)
        print "GMMs",
        print len(self.backend.gmmset.gmms)
  
  

class Login(QDialog):
   CONV_INTERVAL = 0.4
   CONV_DURATION = 1.5
   CONV_FILTER_DURATION = CONV_DURATION
   FS = 8000
   TEST_DURATION = 3
   def __init__(self, parent=None):
	QWidget.__init__(self, parent)
        uic.loadUi("login.ui", self)
	self.userdata =[]
        #self.statusBar()
	self.pushButton.clicked.connect(self.login)
	self.backend = ModelInterface()
	fs, signal = read_wav("bg.wav")
        self.backend.init_noise(fs, signal)
	self.start_record.clicked.connect(self.start_reco_record)
	self.voice_login.clicked.connect(self.stop_reco_record)

   def login(self):
	with open("avatar/metainfo.txt") as db:
            for line in db:
		print line
                tmp = line.split('|')
                print "Check User", tmp[0]
            	if self.user.displayText() == tmp[0] and self.password.displayText() == tmp[3]:
			self.accept()
		#else:
		#	return 0




    ###### RECOGNIZE
   def add_record_data(self, i):
        self.recordData.append(i)
        return self.stopped
	
   def start_reco_record(self):
	fname = "model/tranning.txt"
        if fname:
            try:
                self.backend = ModelInterface.load(fname)
            except Exception as e:
                #self.warn(str(e))
		print "Error"
            else:
                print("Loaded from file: " , fname)
	print "Start Login Record"
        self.recoRecordData = np.array((), dtype=NPDtype)
        #self.start_record()
	print "Starting Recording"
        self.pyaudio = pyaudio.PyAudio()
	self.recordData = []
        self.stream = self.pyaudio.open(format=FORMAT, channels=1, rate=Main.FS,
                        input=True, frames_per_buffer=1)
        self.stopped = False
        self.reco_th = RecorderThread(self)
        self.reco_th.start()

   def stop_reco_record(self):
        self.stopped = True
        self.reco_th.wait()
        #self.timer.stop()
        self.stream.stop_stream()
        self.stream.close()
        self.pyaudio.terminate()
        signal = np.array(self.recordData, dtype=NPDtype)
        self.reco_remove_update(Main.FS, signal)

   def reco_do_predict(self, fs, signal):
        label = self.backend.predict(fs, signal)
        if not label:
            label = "Nobody"
	else:
	    self.accept()
        print label
        

   def reco_remove_update(self, fs, signal):
        new_signal = self.backend.filter(fs, signal)
        print "After removed: {0} -> {1}".format(len(signal), len(new_signal))
        self.recoRecordData = np.concatenate((self.recoRecordData, new_signal))
        real_len = float(len(self.recoRecordData)) / Main.FS / Main.TEST_DURATION * 100
        if real_len > 100:
            real_len = 100

        self.reco_do_predict(fs, self.recoRecordData)


if __name__ == "__main__":
    app = QApplication(sys.argv)

   
   
    
   	 
    ll=Login()
    ll.show()
    
    if ll.exec_()==QtGui.QDialog.Accepted:
	mapp = Main()
	mapp.show()
    	sys.exit(app.exec_())

# RF analysis script

import subprocess # needed for hackrf sweep
import sys # needed for rabbit
import os # needed for file stuff
import time # needed for sleep
from threading import Thread # needed for threads

import pika # needed for rabbitMQ

class Osprey:
    """
    Class to handle RF stuff
    """

    def __init__(self, minFreq=1, maxFreq=6000, ampEnable=1, lnaGain=40, vgaGain=30, binSize=100000, dbmAdjust=0):
        """
        Initalization method

        Args:
            minFreq (int, optional): The min frequency to scan in MHz. Defaults to 1.
            maxFreq (int, optional): The max frequency to scan in MHz. Defaults to 6000.
            ampEnable (int, optional): 0 to disable amplifer, anything else to enable. Defaults to 1.
            lnaGain (int, optional): LNA gain (0-40 dB). Defaults to 40.
            vgaGain (int, optional): VGA gain (0-62 dB). Defaults to 40.
            binSize (int, optional): The width of each frequency bin in Hertz. Defaults to 100000.
            dbmAdjust (float, optional): Adds to the calculated power cutoff for minimum dBm to be considered a signal. Defaults to 0.
        """

        # rabbitMQ setup
        self.connection = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
        self.channel = self.connection.channel()
        self.channel.exchange_declare(exchange='signalSweep', exchange_type='fanout')
        
        # variable setup
        self.minFreq = int(minFreq)
        self.maxFreq = int(maxFreq)
        self.lnaGain = int(lnaGain)
        self.vgaGain = int(vgaGain)
        self.binSize = int(binSize)
        self.dbmAdjust = float(dbmAdjust)

        # set amp enable field
        if ampEnable >= 1:
            self.ampEnable = 1
        else:
            self.ampEnable = 0

    
    def sweepFrequencies(self):
        ''' spawns the hackrf_sweep process and then acts on its output '''

        self.bigSweep = subprocess.Popen(["hackrf_sweep", f"-g {str(self.vgaGain)}", f"-l {str(self.lnaGain)}", f"-a {str(self.ampEnable)}", f"-f {str(self.minFreq)}:{str(self.maxFreq)}", f"-w {str(self.binSize)}"], stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
        #self.bigSweep = subprocess.Popen(["hackrf_sweep", "-f 1:6000", "-w 1000000"], stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)

        startFreq = str(self.minFreq * 1000000) # minFreq is in MHz, but output is in Hz

        tempFloor = float(0)
        counter = 0
        tempFreq = []
        tempDBm = []
        noiseFloor = float(-50)

        # temp variables for high power stuff
        tempPowerFloor = float(0)
        counterPwr = 0
        tempPwr = []
        tempDBmPwr = []
        highPowerFloor = float(-40)

        while True:
            #try:
            splitStr = self.bigSweep.stdout.readline().split(", ")
            #print(str(splitStr))

            if len(splitStr) >= 11: # reading a data string

                tempFloor = tempFloor + float(splitStr[6]) + float(splitStr[7]) + float(splitStr[8]) + float(splitStr[9]) + float(splitStr[10])
                counter = counter + 5

                if splitStr[2] == startFreq: # check if a loop has finished

                    # update noise floor
                    if counter > 0: # small edge case that counter is 0
                        noiseFloor = (tempFloor / counter)
                    if counterPwr > 0: # small edge case that counter is 0
                        highPowerFloor = (tempPowerFloor / counterPwr) + self.dbmAdjust

                    # publish list on rabbitMQ TODO: Change this
                    #self.publishLists(tempFreq, tempDBm, tempPwr, tempDBmPwr)
                    
                    # display info for debugging
                    localTime = time.asctime(time.localtime(time.time()))
                    print("\nLoop completed at: " + localTime)
                    print("New noise floor: " + str(noiseFloor))
                    print(f"Total Targets: {len(tempFreq)}")
                    print(f"New high power floor: {str(highPowerFloor)}")
                    print(f"Total High Power Targets: {str(len(tempPwr))}")

                    # Reset temp variables
                    counter = float(0)
                    tempFloor = float(0)
                    tempFreq = []
                    tempDBm = []

                    tempPowerFloor = float(0)
                    counterPwr = 0
                    tempPwr = []
                    tempDBmPwr = []
             
                if float(splitStr[6]) > noiseFloor: # First freqency is worth checking out
                    tempFreq.append(int(splitStr[2]) + (0 * round(float(splitStr[4]))))
                    tempDBm.append(float(splitStr[6]))

                    # update High Power Counter
                    tempPowerFloor = tempPowerFloor + float(splitStr[6])
                    counterPwr = counterPwr + 1

                    if float(splitStr[6]) > highPowerFloor: # First freqency is worth checking out for HighPwr
                        tempPwr.append(int(splitStr[2]) + (0 * round(float(splitStr[4]))))
                        tempDBmPwr.append(float(splitStr[6]))
                if float(splitStr[7]) > noiseFloor: # Second freqency is worth checking out
                    tempFreq.append(int(splitStr[2]) + (1 * round(float(splitStr[4]))))
                    tempDBm.append(float(splitStr[7]))

                    # update High Power Counter
                    tempPowerFloor = tempPowerFloor + float(splitStr[7])
                    counterPwr = counterPwr + 1

                    if float(splitStr[7]) > highPowerFloor: # Second freqency is worth checking out for HighPwr
                        tempPwr.append(int(splitStr[2]) + (1 * round(float(splitStr[4]))))
                        tempDBmPwr.append(float(splitStr[7]))

                if float(splitStr[8]) > noiseFloor: # Third freqency is worth checking out
                    tempFreq.append(int(splitStr[2]) + (2 * round(float(splitStr[4]))))
                    tempDBm.append(float(splitStr[8]))

                    # update High Power Counter
                    tempPowerFloor = tempPowerFloor + float(splitStr[8])
                    counterPwr = counterPwr + 1

                    if float(splitStr[8]) > highPowerFloor: # First freqency is worth checking out for HighPwr
                        tempPwr.append(int(splitStr[2]) + (2 * round(float(splitStr[4]))))
                        tempDBmPwr.append(float(splitStr[8]))

                if float(splitStr[9]) > noiseFloor: # Fourth freqency is worth checking out
                    tempFreq.append(int(splitStr[2]) + (3 * round(float(splitStr[4]))))
                    tempDBm.append(float(splitStr[9]))

                    # update High Power Counter
                    tempPowerFloor = tempPowerFloor + float(splitStr[9])
                    counterPwr = counterPwr + 1

                    if float(splitStr[9]) > highPowerFloor: # Fourth freqency is worth checking out for HighPwr
                        tempPwr.append(int(splitStr[2]) + (3 * round(float(splitStr[4]))))
                        tempDBmPwr.append(float(splitStr[9]))

                if float(splitStr[10]) > noiseFloor: # Fifth freqency is worth checking out
                    tempFreq.append(int(splitStr[2]) + (4 * round(float(splitStr[4]))))   
                    tempDBm.append(float(splitStr[10]))

                    # update High Power Counter
                    tempPowerFloor = tempPowerFloor + float(splitStr[10])
                    counterPwr = counterPwr + 1

                    if float(splitStr[10]) > highPowerFloor: # Fifth freqency is worth checking out for HighPwr
                        tempPwr.append(int(splitStr[2]) + (4 * round(float(splitStr[4]))))
                        tempDBmPwr.append(float(splitStr[10]))                 
                
            else:
                print("Something went wrong with splitting bigSweep response")
                print(str(splitStr))
                self.bigSweep.kill()
                self.connection.close()
                sys.exit()

    def startSweeper(self):
        ''' spawns all the sweeper threads'''

        self.sweepThread = Thread(target=self.sweepFrequencies, daemon=False)
        self.sweepThread.start()
        


if __name__ == "__main__":

    sweeper = Osprey()

    sweeper.startSweeper()
import time
import os

import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from tqdm import trange

import chipwhisperer as cw
from chipwhisperer.capture import targets
from chipwhisperer.capture.targets._leia import CommandAPDUStruct

USE_CW_SCOPE = False


scope = cw.scope()
target = cw.target(scope, type=targets.LeiaTarget)

if USE_CW_SCOPE:
    # setup scope parameters
    scope.gain.gain = 45
    scope.adc.samples = 5000
    scope.adc.offset = 0
    scope.adc.basic_mode = "rising_edge"
    scope.clock.clkgen_freq = 7370000
    scope.clock.adc_src = "clkgen_x4"
    scope.trigger.triggers = "tio4"
    scope.io.hs2 = "clkgen"

ktp = cw.ktp.Basic(target=target)

traces = []
textin = []
keys = []

N = 50

target.init()
target.configure()
target.set_trigger_strategy(0,[target.TRIG_PRE_SEND_APDU_FRAGMENTED_T0],0)
target.set_trigger_strategy(1,[target.TRIG_PRE_SEND_APDU_SIMPLE_T0],0)


def loadEncryptionKey(target, key):
    apdu = CommandAPDUStruct(
        cla=0x00, ins=0x01, p1=0x00, p2=0x00, lc=0x00, le=0x00, send_le=1
    )
    resp = target.send_APDU(apdu)


def loadInput(target, key):
    pass


def go(target):
    pass


def readOutput(target):
    pass


for i in trange(N, desc="Capturing traces"):
    # run aux stuff that should come before trace here

    key, text = ktp.newPair()
    textin.append(text)
    keys.append(key)

    target.reinit()

    if USE_CW_SCOPE:
        scope.arm()

    loadEncryptionKey(target, key)
    loadInput(target, key)

    go(target)

    timeout = 50
    # wait for targe to finish
    while target.isDone() is False and timeout:
        timeout -= -1
        time.sleep(0.01)

    if USE_CW_SCOPE:
        try:
            ret = scope.capture()
            if ret:
                print("Timeout happened during acquisition")
        except IOError as e:
            print(f"IOError: {e}")

    # run aux stuff that shoud happen after trace here

    _ = readOutput(target)
    
    if USE_CW_SCOPE:
        traces.append(scope.getLastTrace())

trace_array = np.asarray(
    traces
)  # if you prefer to work with numpy array for number crunching
textin_array = np.asarray(textin)
known_keys = np.asarray(keys)  # for fixed key, these keys are all the same

now = datetime.now()
fmt_string = "{:02}{:02}_{}.npy"
trace_file_path = fmt_string.format(now.hour, now.minute, "traces")
textin_file_path = fmt_string.format(now.hour, now.minute, "textins")
keys_file_path = fmt_string.format(now.hour, now.minute, "keys")

print(
    f"Saving results to {trace_file_path}, {textin_file_path} and {keys_file_path}...",
    end="",
)
# save to a files for later processing
np.save(trace_file_path, trace_array)
np.save(textin_file_path, textin_array)
np.save(keys_file_path, known_keys)
print("Done")

# show an example trace
plt.plot(traces[0])
plt.show()

# cleanup the connection to the target and scope
scope.dis()
target.dis()

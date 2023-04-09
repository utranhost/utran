import os
os.sys.path.append(os.path.abspath('./'))
os.sys.path.append(os.path.abspath('../'))


import utran

client = utran.Client(uri='utran://127.0.0.1:8081')

@client
def main():
    res = client.subscribe(['good','study'],lambda msg,topic:print(msg,topic))
    print(res)

    res = client.call(ignore=True).ad0d(1,2)
    print(res)

    res = client.call.add(1,5)
    print(res)

    res = client.unsubscribe(*['good','study'])
    print(res)
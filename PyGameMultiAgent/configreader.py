def readConfig():
    f = open('Config.txt')
    line = f.readline()
    config = {}
    while line:
        k, v = line.split(' ')
        if v == 'True':
            config[k] = True
        elif v == 'False':
            config[k] = False
        else:
            config[k] = float(v)
        line = f.readline()
    f.close()
    return config

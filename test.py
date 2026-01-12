class Test:
    __private = 1

print([x for x in dir(Test) if 'private' in x])

from anki.collection import Collection
from time import sleep
def tryOpenCollection(path, retries=10):
    for _ in range(retries):
        try:
            col = Collection(path)
            return col
        except:
            sleep(0.1)
    raise Exception("Could not open collection")
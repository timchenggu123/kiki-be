#This library helps with interacting with the Anki databases.
from anki.collection import Collection
from anki.consts import *
def getTodayStudiedCards(col: Collection):
    """
    The fields the revlog table from pragma table_info('revlog') are:
    [[0, 'id', 'INTEGER', 0, None, 1], [1, 'cid', 'INTEGER', 1, None, 0], [2, 'usn', 'INTEGER', 1, None, 0], [3, 'ease', 'INTEGER', 1, None, 0], [4, 'ivl', 'INTEGER', 1, None, 0], [5, 'lastIvl', 'INTEGER', 1, None, 0], [6, 'factor', 'INTEGER', 1, None, 0], [7, 'time', 'INTEGER', 1, None, 0], [8, 'type', 'INTEGER', 1, None, 0]]
    """
    ### For some insane reason, the ID FIELD is actually the timestamp of when the card is studied. Insane. 
    ### The cid field is the card ID. 
    ### The consts for revlog types are REVLOG_LRN REVLOG_REV REVLOG_RELRN REVLOG_CRAM`
    latest_cls = f"SELECT max(id) as max_id FROM revlog WHERE id > {(col.sched.day_cutoff - 86400)*1000} GROUP BY cid"
    latest_cards_qry = f"SELECT cid, id, type FROM revlog WHERE id IN ({latest_cls})"
    latest_cards = col.db.all(latest_cards_qry)
    return latest_cards
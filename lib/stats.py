from anki.collection import Collection

def deck_card_stats(col: Collection, did: int) -> str:# graph data
        col.decks.select(did)
        stats=col.stats()
        maturity_raw = stats._cards() #Four fields: mature, young, unseen, and suspended. Suspended is not used right nowl.
        limit = stats._limit()
        # text data
        (c, f) = stats.col.db.first(
            """
select count(id), count(distinct nid) from cards
where did in %s """
            % limit
        )
        (low_ease, avg_ease, high_ease) = stats._factors()
        low_ease = low_ease if low_ease else -1
        avg_ease = avg_ease if avg_ease else -1
        high_ease = high_ease if high_ease else -1
        return {
            "mature": maturity_raw[0],
            "young": maturity_raw[1],
            "unseen": maturity_raw[2],
            "suspended": maturity_raw[3],
            "count": c,
            "unique": f,
            "low_ease": low_ease,
            "avg_ease": avg_ease,
            "high_ease": high_ease,
        }
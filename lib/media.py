import re
from anki.sound import TTSTag

def replacePlayTag(txt, front_av_files:list, back_av_tags:list):
    expr = re.compile(r"\[anki:(play:(.):(\d+))\]")
    def repl(match: re.Match):
        side = match.group(2)
        if side == 'q':
            files = front_av_files
        else:
            files = back_av_tags
        file = files[int(match.group(3))]
        return f'''
<audio src="{file}" controls></audio>
'''
    return expr.sub(repl, txt)

def isTTSTag(tag):
    if type(tag) == TTSTag:
        return True
    return False
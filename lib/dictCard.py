from anki.collection import Collection

def createDictCardModel(col: Collection):
    m = col.models.new("KikiDictCard")
    fields = [
        "word",
        "phonetic",
        "audio",
        "meanings",
        "origin"
    ]
    for f in fields:
        fld = col.models.new_field(f)
        col.models.add_field(m, fld)

    m["css"] = """.card {
 font-family: Microsoft Yahei;
 background-color: transparent;
 line-height: 200%;
 backgr
 text-align: left;
 color: black;
}
#word{
        padding-top:15px;
}
#answer{
        height:3px;
        color:#073642;
        border-width:0px;
        width: 80%;
        margin:15px auto;
}
#etymology{
        margin:0 8px;
        line-height: 150%;
}
#back{
        margin:10px 10px;
        padding-bottom:10px;
}"""
    qfmt=r"""<center>
<div id="word">
<span style="font-size: 48px;">{{word}}
</span>
<br>
<span style="font-family:'Lucida Sans Unicode',Arial;font-size: 20px;">{{phonetic}}</span>
<br>
<audio src="{{audio}}" controls></audio>
</div>
</center>"""
    afmt="""{{FrontSide}}

<hr id="answer">
<div id="back">
<p><span style="font-size: 18px;">{{meanings}}</span></p>
<div id='etymology'><p style='font-family: Georgia, Garamond, Times New Roman, Times, serif; font-size: 16px;'>{{origin}}</p></div>
</div>"""
    tmpl = col.models.new_template("DictCard")
    tmpl["qfmt"] = qfmt
    tmpl["afmt"] = afmt
    tmpl["ord"] = 0
    col.models.add_template(m, tmpl)
    col.models.add(m)
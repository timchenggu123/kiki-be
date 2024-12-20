import requests

URL =  "https://api.dictionaryapi.dev/api/v2/entries/en/"

# raw =[
#   {
#     "word": "hello",
#     "phonetic": "həˈləʊ",
#     "phonetics": [
#       {
#         "text": "həˈləʊ",
#         "audio": "//ssl.gstatic.com/dictionary/static/sounds/20200429/hello--_gb_1.mp3"
#       },
#       {
#         "text": "hɛˈləʊ"
#       }
#     ],
#     "origin": "early 19th century: variant of earlier hollo ; related to holla.",
#     "meanings": [
#       {
#         "partOfSpeech": "exclamation",
#         "definitions": [
#           {
#             "definition": "used as a greeting or to begin a phone conversation.",
#             "example": "hello there, Katie!",
#             "synonyms": [],
#             "antonyms": []
#           }
#         ]
#       },
#       {
#         "partOfSpeech": "noun",
#         "definitions": [
#           {
#             "definition": "an utterance of ‘hello’; a greeting.",
#             "example": "she was getting polite nods and hellos from people",
#             "synonyms": [],
#             "antonyms": []
#           }
#         ]
#       },
#       {
#         "partOfSpeech": "verb",
#         "definitions": [
#           {
#             "definition": "say or shout ‘hello’.",
#             "example": "I pressed the phone button and helloed",
#             "synonyms": [],
#             "antonyms": []
#           }
#         ]
#       }
#     ]
#   }
# ]

def get_definition(word):
    response = requests.get(URL + word)
    if response.status_code == 200:
        return response.json()
    return None


def parse_phonetics(raw):
    uk_audio = None
    uk_text = None
    us_audio = None
    us_text = None
    other_audio = None
    other_text = None
    for phonetic in raw[0]["phonetics"]:
        text = phonetic.get("text")
        audio = phonetic.get("audio")
        if not audio:
            continue
        if audio.endswith('uk.mp3'):
            uk_text = text
            uk_audio = audio
            return {"audio": uk_audio, "text": uk_text}
        if audio.endswith('us.mp3'):
            us_text = text
            us_audio = audio
            return {"audio": us_audio, "text": us_text}
        other_text = text
        other_audio = audio
        return {"audio": other_audio, "text": other_text}
    return {"audio": None, "text": raw[0]["phonetic"]}

def make_card_from_raw(col, raw):
    word = raw[0]["word"]
    phonetic = parse_phonetics(raw)
    origin = raw[0].get("origin")
    meanings = raw[0].get("meanings")
    front = f"{word} ({phonetic['text']})"
    back = f"{origin}\n\n"
    for meaning in meanings:
        part_of_speech = meaning.get("partOfSpeech")
        definitions = meaning.get("definitions")
        back += f"{part_of_speech}\n"
        for definition in definitions:
            definition_text = definition.get("definition")
            example = definition.get("example")
            back += f"- {definition_text}\n"
            if example:
                back += f"  - {example}\n"
    model = col.models.by_name("Basic")
    note = col.new_note(model)
    note.fields[0] = front
    note.fields[1] = back
    return note
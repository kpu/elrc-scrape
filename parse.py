#!/usr/bin/env python
# A voodoo interpreter of ELRC-SHARE.
# ELRC metadata is sequentially numbered.  5000 is higher than their maximum when this was written.
NUM_MAX=5000
import json
import os
import re
import sys
import zipfile
from xml.etree import ElementTree

from typing import List

# These already exist in OPUS.
def already_on_opus(name):
    if "Tatoeba" in name:
        return True
    if "Global Voices" in name:
        return True
    if "ParaCrawl " in name:
        return True
    if name.startswith("Europat") or name.startswith("EuroPat"):
        return True
    return False

# Sometimes JSON gives you a list, sometimes one element.  Make it always a list.
def list_if_not(arg):
    if isinstance(arg, list):
        return arg
    return [arg]

def possibly_empty_list(above, key):
    try:
        return list_if_not(above[key])
    except KeyError:
        return []

STOPWORDS = set(w.lower() for w in ['of', 'Bilingual', 'the', 'COVID-19', 'from', 'corpus', '(Processed)', '-', 'dataset', 'and', 'dataset.', 'parallel', 'Multilingual', 'website', 'release', 'in', '(EN,', 'Parallel', 'FR,', 'for', 'ES,', 'on', 'EU', 'Dictionary', 'domain', 'The', 'Ministry', 'DE,', 'terminology', 'glossary', 'Republic', 'Office', 'European', '(EN-FR)', 'IT,', 'Glossary', 'PT,', 'Corpus', 'National', 'Polish-English', '(EN-ES)', 'English', 'terms', 'v2', 'documents', 'Monolingual', '(English', 'Termcat', 'Public', 'EN,', 'Agency', 'PL,', 'Publications', 'project', 'Croatian-English', 'Terms', 'Evroterm', 'English-Norwegian', '(EN-DE)', 'EUROPARL', 'terms,', 'Anonymised', 'texts', 'Organization', 'RU,', 'HU,',  'EL,', 'Βilingual', 'case', 'data', 'IP', 'FI,', 'Esterm.', 'Website', 'website', '.', 'with', 'resource', 'Web', 'Site', 'Translation', 'Memories', 'content', 'memory', 'bilingue', 'translations', 'TMX', 'contents', 'TM', 'field', '–', 'concerning', 'Trilingual', 'related', 'to', 'PDF', 'PDFs', 'word', 'Memorias', 'traducción', 'de'])
def stop_word(word):
    if word.lower() in STOPWORDS:
        return True
    if word.startswith("(") or word.endswith(')'):
        return True
    # Usually languages
    if '-' in word:
        try:
            # Allow year ranges
            int(word.split('-')[0])
            return False
        except ValueError:
            return True
    if len(word) == 0:
        return True
    return False

def heuristic_short_name(name : str):
    name = name.replace(',', '').replace("’s", '').replace("'s", '').replace('/', ' ').replace('&', ' ').replace('"', ' ').replace("U.S.", "US").replace("'", '').replace("State-related", "State").replace("Anti-Corruption", "Anticorruption").replace("Secretariat-General", "Secretariat_General")
    split = name.split(' ')
    ret = '_'.join([n for n in split if not stop_word(n)])
    if len(ret) == 0:
        if name.endswith(" website parallel corpus (Processed)") and '-' in split[0]:
             return "government_websites_" + name.split(' ')[0].replace('-', '_')
    return ret.replace('-', '_')

class Corpus:
    def __init__(self, number : int, json_data):
        self.number = number
        self.json_data = json_data
        # Extract name, preferably in English.
        names = list_if_not(json_data["resourceInfo"]["identificationInfo"]["resourceName"])
        self.name = names[0]["#text"]
        for n in names:
            if n["@lang"] == "en":
                self.name = n["#text"]
        #Feel bad about this, maybe some headword extraction
        self.shortname = heuristic_short_name(self.name)
        self.processed_name = self.name.endswith("(Processed)")
        self.info_url = json_data["resourceInfo"]["identificationInfo"]["url"]

        # Extract relations.
        self.versions = []
        self.aligned_annotated = []
        self.part_of = []
        self.has_part = []
        self.is_aligned_version_of = []
        for relation in possibly_empty_list(json_data["resourceInfo"], "relationInfo"):
            relation_type = relation["relationType"]
            relation_with = relation["relatedResource"]["targetResourceNameURI"]
            try:
                relation_with = int(relation_with)
            except ValueError as e:
                # WTF
                if relation_with == "https://www.nb.no/sbfil/tekst/20150601_ud.tar.gz":
                    continue
                relation_hotfix = {
                    'MARCELL Croatian legislative subcorpus' : 2645,
                    'PRINCIPLE Ciklopea Croatian-English Parallel Corpus of Railway Procurement Documents' : 4289,
                    'PRINCIPLE SDURDD Croatian-English Procurement Parallel Corpus' : 4369,
                    'PRINCIPLE DKOM Croatian-English Parallel Corpus of Directives of the European Parliament and of the Council': 4291,
                    'PRINCIPLE Central Public Procurement Office of Republic of Croatia Croatian-English Procurement Parallel Corpus' : 4292,
                    'PRINCIPLE Ciklopea Croatian-English Parallel Corpus of Manuals for Medical Devices' : 4313,
                    'Foras na Gaeilge parallel translation memory dataset (evaluated)' : 4320,
                    'Foras na Gaeilge parallel translation memory dataset' : 4326,
                    'Dept of Justice parallel English-Irish secondary legislation (evaluated)' : 4328,
                    'Dept of Justice parallel English-Irish secondary legislation' : 4321,
                    'PRINCIPLE MVEP Croatian-English Parallel Corpus of legal documents' : 4329,
                    'PRINCIPLE MVEP Croatian-English-German Glossary of Legal Terms' : 4315,
                    'PRINCIPLE An tAonad Aistriúcháin agus Ateangaireachta ÓEG/NUIG Translation Unit dataset' : 4339,
                    'PRINCIPLE English-Irish parallel primary legislation 1960 to 1989' : 4341,
                    "PRINCIPLE English-Irish parallel primary legislation 1990 to 2019" : 4345,
                    'PRINCIPLE English-Irish parallel secondary legislation' : 4340,
                    "PRINCIPLE English-Irish Houses of the Oireachtas ancillary material dataset" : 4342,
                    'PRINCIPLE English-Irish glossary of terms relating to primary legislation in Ireland' : 4354,
                    'PRINCIPLE English-Irish Annual Reports from the Houses of the Oireachtas' : 4344,
                    'https://elrc-share.eu/repository/browse/translation-memory-from-standards-norway/15e913c2c8f711eb9c1a00155d026706360ec3dab20847439f88dbe61662980c/' : 4349,
                    'https://elrc-share.eu/repository/browse/translation-memories-from-the-mfa-2020/15e913c4c8f711eb9c1a00155d026706224b3bc86b2c4e2eaa7a794367e171e8/' : 4351,
                    'https://elrc-share.eu/repository/browse/translation-memories-from-the-ministry-of-foreign-affairs-of-norway/7c20eaf50a6d11e7bfe700155d020502df3a09319a164b74bb5c70bce85de0a9/' : 305,
                    'The Icelandic Met Office - Weather forecasts and warnings' : 4325,
                    'Icelandic Standards - TM and Lexicon 2020' : 4335,
                    'The Translation Centre of the Icelandic Ministry for Foreign Affairs – Gullsarpur' : 4318,
                    'The Translation Centre of the Icelandic Ministry for Foreign Affairs – eProcurement' : 4317,
                    "https://elrc-share.eu/repository/browse/hrenwac-croatian-english-parallel-corpus/3417cfdabbf211eb9c1a00155d026706a6ca797b6ac84074b09ae00bf29b53a8/" : 4294,
                }
                relation_with = relation_hotfix[relation_with]
            # If they aligned it for us, don't bother.
            if relation_type in ["hasAlignedVersion", "hasAnnotatedVersion", "hasConvertedVersion"]:
                self.aligned_annotated.append(relation_with)
            # hasVersion and isVersionOf is very messy.  It could mean revised version or processed.
            elif relation_type == "hasVersion" or relation_type == "isVersionOf":
                self.versions.append(relation_with)
            elif relation_type == "isPartOf":
                self.part_of.append(relation_with)
            elif relation_type == "hasPart":
                self.has_part.append(relation_with)
            elif relation_type == "isAlignedVersionOf":
                self.is_aligned_version_of.append(relation_with)
        self.rejected = None
        self.parse_and_reject()

    def wget(self):
        if self.post:
            post = " --post-data='" + self.post + "'"
        else:
            post = ""
        return "wget -O " + str(self.number) + ".zip" + post + ' ' + self.download

    def reject(self, message):
        self.rejected = message
        print(f"Reject {self.number}: {self.rejected}: {self.name}", file=sys.stderr)

    # These are very open licenses with attribution that stupidly require a post.
    REQUIRES_POST=set(["Apache-2.0"])

    def parse_and_reject(self):
        if already_on_opus(self.name):
            self.reject("Already on OPUS")
            return
        j = self.json_data
        # Only care about corpora not software, termbanks, or MT systems
        if "corpusInfo" not in j["resourceInfo"]["resourceComponentType"].keys():
            self.reject("Not a corpus")
            return
        # If it's not downloadable, pass
        if "distributionInfo" not in j["resourceInfo"].keys():
            self.reject("No download information")
            return
        locations = set()
        self.licenses = set()
        for loc in j["resourceInfo"]["distributionInfo"]:
            for l in loc["licenceInfo"]:
                self.licenses.add(l["licence"])
            # Skip stuff missing an actual location
            if "downloadLocation" not in loc.keys():
                continue
            download = loc["downloadLocation"]
            locations.update(list_if_not(loc["downloadLocation"]))

        # There's distribution information but nothing to download
        if len(locations) == 0:
            self.reject("Nothing to download")
            return
        # Only ParaCrawl abused the multiple locations functionality.
        assert len(locations) == 1
        self.download = locations.pop()
        # These redirect except the URLs that require a POST break.
        if self.download.startswith("https://elrc-share.eu/repository/download/"):
            self.download += "/"
        if self.download.startswith("https://elrc-share.eu/repository/download/") and not self.licenses.isdisjoint(self.REQUIRES_POST):
            intersect = self.licenses.intersection(self.REQUIRES_POST)
            assert len(self.licenses) == 1 # Not sure what to do with POST if there are two licenses
            self.post = "licence_agree=on&in_licence_agree_form=True&licence=" + list(self.licenses)[0]
        else:
            self.post = None
        self.linguality = set()
        self.languages = set()
        for info in j["resourceInfo"]["resourceComponentType"]["corpusInfo"]["corpusMediaType"]["corpusTextInfo"]:
           for l in info["languageInfo"]:
               self.languages.add(l["languageId"].split('-')[0])
           linguality = info['lingualityInfo']['lingualityType']
           self.linguality.add(linguality)
           if linguality == "multilingual" and 'multilingualityType' in info['lingualityInfo'] and info['lingualityInfo']['multilingualityType'] in ['other', 'comparable']:
               self.reject(f"multilingualityType is {info['lingualityInfo']['multilingualityType']}")
               return
           try:
               url = info["creationInfo"]["originalSource"]["targetResourceNameURI"]
               if url.startswith("http"):
                   if self.number == 937:
                       url = "https://vp1992-2001.president.ee" # Incorrect metadata
                   # Sadly some domains will be broken with _
                   self.shortname = url.split('/')[2].replace('-', '_')
           except (KeyError, TypeError):
               pass
           

        self.linguality = set(info['lingualityInfo']['lingualityType'] for info in j["resourceInfo"]["resourceComponentType"]["corpusInfo"]["corpusMediaType"]["corpusTextInfo"])
        # Currently only parallel corpora
        if "bilingual" not in self.linguality and "multilingual" not in self.linguality:
            self.reject("Not a parallel corpus")
            return
        if len(self.aligned_annotated) != 0:
           self.reject("There's an aligned or annotated version")
           return

def load_corpus(number):
    file_name = str(number) + ".json"
    # ELRC returns a 500 error with empty json if the corpus doesn't exist.
    if os.stat(file_name).st_size == 0:
        return None
    with open(file_name, "r") as f:
        j = json.load(f)
    return Corpus(number, j)

def load_metadata():
    corpora = [load_corpus(i) for i in range(NUM_MAX)]
    remaining = [c for c in corpora if c and c.rejected is None]

    # Go through version relationships.  If one of the versions is "(Processed)", prefer that.
    for corpus in remaining:
        for version in corpus.versions:
            if corpora[version] is None:
                print(f"Version reference from {corpus.number} to {version} is broken.", file=sys.stderr)
                continue
            if corpora[version].processed_name or corpus.processed_name:
                if corpora[version].processed_name and corpus.processed_name:
                    raise Exception(f"Two corpora claim to be processed with a version relation: {corpus.number} {version}")
                if corpus.processed_name:
                    winner = corpus
                    loser = corpora[version]
                else:
                    winner = corpora[version]
                    loser = corpus
                if winner.rejected and not loser.rejected:
                    # Erroneous processed version
                    if loser.number == 29 and winner.number == 1086:
                        continue
                    raise Exception(f"Processed version {version} of {corpus.number} is rejected.")
                loser.reject(f"{winner.number} is a processed version")
    remaining = [c for c in remaining if c.rejected is None]

    for corpus in remaining:
       alive_versions = [v for v in corpus.versions if corpora[v] and corpora[v].rejected is None]
       if len(alive_versions) != 0:
           print(f"Version information for {corpus.number} \"" + corpus.name + "\" suggests there are other versions:", file=sys.stderr)
           for version in alive_versions:
               print("   " + corpora[version].name, file=sys.stderr)
    remaining = [c for c in remaining if c.rejected is None]

    # Find multilingual corpora that have subparts and reject the multilingual part which is just a zip of all of them.  We prefer only downloading what's necesssary and also a zip of zips is annoying.
    for corpus in remaining:
        if "multilingual" in corpus.linguality and len(corpus.has_part) != 0:
            # Khresmoi has a phantom EN-PL that's rejected
            if corpus.number == 1091:
                continue
            for p in corpus.has_part:
                # 3382 is v1 labeled as part of v2 alongside other corpora.
                if corpora[p].rejected and p != 3382:
                    raise Exception(f"Part of accepted multilingual corpus #{corpus.number} {corpus.name} was rejected: #{p} {corpora[p].name}")
            corpus.reject("Multilingual bundle has smaller parts")
    return corpora

def hotfix_metadata(corpora):
    # Reject insufficiently annotated v1 multilingual corpora that have a v2.
    for old in [
        2923, #COVID-19 EUROPARL dataset v1.
        3382, #COVID-19 EU presscorner v1 dataset.
        2681, #Publications Office of the EU on the medical domain 2730 is v2
    ]:
        for part in corpora[old].has_part:
            corpora[part].reject("Dataset v1 has a v2")
        corpora[old].reject("Dataset v1 has a v2")
    
    # I think these are subsumbed by:
    # 2541 English-Croatian translation memory from the Ministry of Regional Development and EU Funds (Processed)
    # 2542 English-Croatian translation memory from the Ministry of Agriculture (Processed)
    for extra_part in [
        2386, #Croatian-English translation memory from the Ministry of Regional Development and EU Funds (Part 1) (Processed)
        2387, #Croatian-English translation memory from the Ministry of Regional Development and EU Funds (Part 2) (Processed)
        2389, #Croatian-English translation memory from the Ministry of Agriculture (Part 1) (Processed)
        2390, #Croatian-English translation memory from the Ministry of Agriculture (Part 2) (Processed)
    ]:
        corpora[extra_part].reject("Part of a larger corpus but not labeled as such")
    corpora[1091].reject("Khresmoi is in mtdata directly from lindat instead of the ELRC version that only pairs with English")
    if corpora[1834]:
        corpora[1834].reject("test XML")
    corpora[2654].reject("post-editing training data")
    corpora[4244].reject("Download broken")
    corpora[2606].reject("XLIFF format; TMX is supposed to be available as 2610 but that is not available for download yet and the corpus is too small to bother with an XLIFF parser")
    corpora[2483].reject("Unaligned text file")
    for i in [3858, 3859, 3860, 3861, 3862, 3864]:
        if corpora[i]:
            corpora[i].reject("Same download location as EMEA.")
    corpora[3836].reject("TODO: extract from this non-standard format")
    corpora[3969].reject("TODO: can't be bothered to parse a non-standard format for 563 sentence pairs")
    corpora[2646].reject("TODO: nested zip files, ugh")
    corpora[3081].reject("sh language code causes conflict with other part of data set https://en.wikipedia.org/wiki/Serbo-Croatian#ISO_classification")
    #Multilingual corpus in HEALTH (COVID-19) domain part_1a (v.1.0) when Multilingual corpus in HEALTH (COVID-19) domain part_1a (v.1.05) exists
    for old_health in [3858, 3861, 3862, 3863, 3866, 3867, 3870, 3872]:
        if corpora[old_health]:
            corpora[old_health].reject("Old version")
    
    # Have TMX in a language but not in the metadata
    corpora[416].languages.add("sr")
    corpora[416].languages.add("el")
    
    # Nicer names for multilingual corpora
    for parent, name in [
        (3192, 'antibiotic'),
        (2682, 'EMEA'),
        (3550, 'presscorner_covid'),
        (2865, 'EU_publications_medical_v2'),
        (3549, "EUR_LEX_covid"),
        (3448, "EC_EUROPA_covid"),
        (3254, "EUROPARL_covid"),
        (2922, "wikipedia_health"),
        (2730, "vaccination"),
    ]:
        if not corpora[parent]:
            print(name)
        combined = corpora[parent].versions + corpora[parent].aligned_annotated + corpora[parent].has_part
        for v in combined:
            corpora[v].shortname = name
    # Multilingual corpus is a hidden json
    for c in corpora:
        if c and c.is_aligned_version_of == [1134]:
            c.shortname = "EUIPO_2017"
        if c and c.part_of == [704]:
            c.shortname = "EUIPO_list"


    #corpora[948].reject("Too much Greek copied to target")
    corpora[835].reject("Poor quality")
    for i in [784, 801, 804, 807, 816, 805, 806, 808, 846, 863]:
        corpora[i].reject("Text was inserted into the TMX without escaping and therefore the TMX is not well-formed; notified ELRC")
    corpora[1973].reject("The XML standard forbids character entity &#5; https://www.w3.org/TR/xml/#charsets This entity appears at line 61972, column 211")
    corpora[1077].reject("The XML standard forbids character entity &#21; https://www.w3.org/TR/xml/#charsets This entity appears at line 1122323, column 13")
    corpora[2580].reject("TODO: UTF16 encoded TMX")
    corpora[4363].reject("Corpus cleaning training data")
    for i in [4289, 4290, 4291, 4292, 4293, 4312, 4316, 4321, 4328, 4330, 4332, 4340, 4341, 4342, 4344, 4345, 4346, 4352, 4353, 4369, 4598, 4599, 4600, 4601, 4604]:
        corpora[i].reject("PRINCIPLE doesn't build TMX")
    for i in [4325]:
        corpora[i].reject("ZIP within a ZIP")
    corpora[4609].reject("tarball within a zip")
    for i in [4405, 4406, 4407, 4408, 4409, 4410, 4411, 4412, 4413, 4414, 4415, 4416, 4417, 4418, 4419, 4420, 4421, 4422, 4423, 4424, 4425, 4426, 4427, 4428, 4429, 4430, 4431, 4432, 4433, 4434, 4435, 4436, 4437, 4438, 4439, 4440, 4441, 4442, 4443, 4444, 4445, 4446, 4447, 4448, 4449, 4450, 4451, 4452, 4453, 4454, 4455, 4456, 4457, 4458, 4459, 4460, 4461, 4462, 4463, 4464, 4465, 4466, 4467, 4468, 4469, 4470, 4471, 4472, 4473, 4474, 4475, 4476, 4477, 4478, 4479, 4480, 4481, 4482, 4483, 4484, 4485, 4523, 4524, 4525, 4526, 4527, 4528, 4529, 4530, 4531, 4532, 4533, 4534, 4535, 4536, 4537, 4538, 4539, 4540, 4541, 4542, 4543, 4544, 4545, 4546, 4547, 4548, 4549, 4550, 4551, 4552, 4553, 4554, 4555, 4556, 4557, 4558, 4559, 4560, 4561, 4562, 4563, 4564, 4565, 4566, 4567, 4568, 4569, 4570, 4571, 4572, 4573, 4574, 4575, 4576, 4577, 4578, 4579, 4580, 4581, 4582, 4583, 4584, 4585, 4586, 4587, 4588, 4589, 4590, 4591, 4592, 4593, 4594, 4595, 4596, 4597]:
        corpora[i].reject("NTEU's TMX files are missing TU tags.")

    corpora[416].shortname = "Swedish_Social_Security"
    corpora[417].shortname = "Swedish_Work_Environment"
    corpora[403].shortname = "Rights_Arrested"
    corpora[401].shortname = "Swedish_Labour_Part2"
    corpora[406].shortname = "Swedish_Labour_Part1"
    for corpus in corpora:
        if corpus and corpus.name.startswith("Compilation of ") and corpus.name.endswith(" parallel corpora resources used for training of NTEU Machine Translation engines."):
            corpus.shortname = 'NTEU'
    corpora[422].shortname = 'Portuguese_legislation'
    corpora[471].shortname = 'Bugarian_Revenue'
    corpora[492].shortname = 'Romanian_Wikipedia'
    corpora[511].shortname = 'bokmenntaborgin_is'
    corpora[630].shortname = 'BMVI_Publications'
    corpora[631].shortname = 'BMVI_Website'
    corpora[634].shortname = 'BMI_Brochures_2011_2015'
    corpora[649].shortname = 'Greek_administration'
    corpora[335].shortname = 'government_websites_espt'
    corpora[651].shortname = 'government_websites_Croatian'
    corpora[652].shortname = 'Greek_law'
    corpora[1087].shortname = "German_Foreign_Office_2016_2018"
    corpora[1088].shortname = "German_Foreign_Office_2016"
    corpora[1089].shortname = "German_Foreign_Office_2017"
    corpora[1090].shortname = "German_Foreign_Office_2018"
    corpora[489].shortname = "Secretariat_General_Part1"
    corpora[490].shortname = "Secretariat_General_Part2"
    corpora[770].shortname = "National_Security_Defence"
    corpora[1973].shortname = "Italian_legal_terminology"
    corpora[1945].shortname = "Italian_legal_terminology"
    # There are two of them: 718 and 508.  No idea why.
    corpora[508].shortname = "Tilde_Statistics_Iceland"
    corpora[798].shortname = "Financial_Stability_Bank_Poland_2013_14"
    corpora[799].shortname = "Financial_Stability_Bank_Poland_2015_16"
    corpora[472].shortname = "Polish_Central_Statistical_Publications"
    corpora[1805].shortname += "_ennb"
    corpora[1806].shortname += "_nben"
    corpora[1945].shortname += "_itde"
    corpora[1973].shortname += "_deit"
    corpora[2424].shortname += "_Part1"
    # Ugh names differed by a .  Asked, they said they think it is two different parts due to ELRI limitations.
    for c in [2425, 2613, 2615, 2617, 2624, 2625, 2640, 2642]:
        corpora[c].shortname += "_Part2"


# What files to keep in zip, mostly for sanity checking that we have everything.
def keep_file(n : str):
    if n.endswith('/') or n.endswith("_metadata.txt"):
        return False
    file_name = n.split('/')[-1]
    if file_name.startswith("license") and (file_name.endswith(".txt") or file_name.endswith(".pdf")):
        return False
    if file_name.startswith("resource-") and file_name.endswith(".xml"):
        return False
    if n.startswith("__MACOSX") or n.endswith(".DS_Store"):
        return False
    if n.endswith(".xls") or n.endswith(".xlsx"):
        return False
    # A whole bunch seem to have rejected stuff
    if "rejected/" in n:
        return False
    if n.endswith("ReadMe.txt"):
        return False
    # Validation reports were supposed to be uploaded separately.
    if n == 'ELRC_474_Natolin European Centre Dataset (Processed)_VALREP.pdf' or n == "statistics.csv":
        return False
    return True


# Codes seen in ELRC-SHARE names
MAP639 = {
    "eng" : "en",
    "bul" : "bg",
    "lav" : "lv",
    "ell" : "el",
    "pol" : "pl",
    "ron" : "ro",
    "fra" : "fr",
}

def normalize_language_code(code):
    code = code.split('-')[0].lower()
    if code in MAP639:
        code = MAP639[code]
    return code

# Read first record of TMX to guess languages.  Note this will underreport for files that have different languages in each record like Khresmoi
def sense_tmx_languages(tmx):
    context = ElementTree.iterparse(tmx, events=['end'])
    tus = (el for event, el in context if el.tag == 'tu')
    langs = set()
    count = 0
    for tu in tus:
        for tuv in tu.findall('tuv'):
            langs = langs.union(set(v for k, v in tuv.attrib.items() if k.endswith('lang')))
        count += 1
        if count == 30:
            break
    return set(normalize_language_code(c) for c in langs)

def load_files(corpora : List[Corpus]):
    to_download = []
    remaining = [c for c in corpora if c and c.rejected is None]
    for corpus in remaining:
        f = str(corpus.number) + ".zip"
        corpus.tmx_languages = {}
        try:
            with zipfile.ZipFile(f, 'r') as zipped:
                names = zipped.namelist()
                for n in names:
                    if n.endswith(".tmx") and not n.startswith("__MACOSX"):
                        with zipped.open(n) as tmx:
                            corpus.tmx_languages[n] = sense_tmx_languages(tmx)
            names = [n for n in names if keep_file(n)]
            corpus.files = names
            # Hopefully we didn't delete everything!
            assert len(names) != 0
        except FileNotFoundError:
            to_download.append(corpus)
        except zipfile.BadZipFile:
            print(f"File {f} from {corpus.download} is not a zip file.  Most likely this means the corpus has an open license but ELRC put a click wrap on it for no reason.  Consider adding it to the list of licenses in REQUIRES_POST in the source of this script.", file=sys.stderr)
            corpus.reject(f"Not a ZIP file: {corpus}")
        except ElementTree.ParseError as e:
            corpus.reject(f"Contains a bad TMX file {e}")
    return to_download

def hotfix_files(corpora):
    # Extra text files alongside tmx
    for index in [1796, 1797]:
        corpora[index].files = [f for f in corpora[index].files if not f.endswith(".txt")]
    remaining = [c for c in corpora if c and c.rejected is None]
    for corpus in remaining:
        tmxes = [f for f in corpus.files if f.endswith(".tmx")]
        found_languages = set()
        for tmx in tmxes:
            if not corpus.tmx_languages[tmx].issubset(corpus.languages):
                print(f"Corpus {corpus.number} contains file {tmx} with languages {corpus.tmx_languages[tmx]} that are not in metadata languages {corpus.languages}.  Patching metadata.", file=sys.stderr)
            found_languages = found_languages.union(corpus.tmx_languages[tmx])
        missing = corpus.languages.difference(found_languages)
        if len(missing):
            print(f"Corpus {corpus.number} advertised {missing} that do not appear in the TMXes. Patching metadata.", file=sys.stderr)
        corpus.languages = found_languages


def entry_template(corpus : Corpus, inpaths : List[str], shortname = None, languages = None):
    if languages is None:
        languages = corpus.languages
    if shortname is None:
        if corpus.shortname is None:
            raise Exception(f"Need to assign a shortname for {corpus.number} {corpus.name}")
        shortname = corpus.shortname
    if len(languages) != 2:
        raise Exception(f"Should be 2 languages not {languages} for {corpus.number} {corpus.name}")
    langs = list(languages)
    langs.sort()
    # Currently post is not required for anything
#    if corpus.post:
#        post = corpus.post
#    else:
#        post = ""
    return '\t'.join([langs[0], langs[1], str(corpus.number), shortname, corpus.name.replace("\t", ' '), corpus.info_url, corpus.download, ' '.join(corpus.licenses)] + inpaths)

def parse_language_from_filename(filename, languages):
    filename = filename.replace("en-GB", "en").replace("de-DE", "de").replace("fr-FR", "fr").replace("it-IT", "it").replace("es-ES", "es").replace("pt-PT", "pt")
    split = re.split('[/_. -]', filename)
    if len(split) < 2:
        return None
    for i in range(len(split) - 1):
        if split[i] in languages and split[i+1] in languages:
            return (split[i], split[i+1])
        if split[i] in MAP639.keys() and split[i+1] in MAP639.keys() and MAP639[split[i]] in languages and MAP639[split[i+1]] in languages:
            return (MAP639[split[i]], MAP639[split[i+1]])
    return None

def create_records(corpora: List[Corpus]):
    remaining = [c for c in corpora if c and c.rejected is None]
    for corpus in remaining:
        tmxes = [f for f in corpus.files if f.endswith(".tmx")]
        if corpus.name.startswith("Compilation of ") and corpus.name.endswith(" parallel corpora resources used for training of NTEU Machine Translation engines."):
            langs = list(corpus.languages)
            langs.sort()
            tiera = langs[0] + "-" + langs[1] + "-a.tmx"
            assert tiera in corpus.files
            tierb = langs[0] + "-" + langs[1] + "-b.tmx"
            assert tierb in corpus.files
            yield entry_template(corpus, [tiera], shortname = "NTEU_TierA")
            yield entry_template(corpus, [tierb], shortname = "NTEU_TierB")
        elif len(corpus.files) == 1 and corpus.files[0].endswith(".tmx") and len(corpus.languages) == 2:
            # Sane corpora, thank you!
            yield entry_template(corpus, corpus.files)
        elif len(corpus.files) == 1 and corpus.files[0].endswith(".tmx") and len(corpus.languages) > 2:
            # There are 3 multi-lingual corpora that use a single TMX.
            langs = list(corpus.languages)
            langs.sort()
            for i, l1 in enumerate(langs):
                for l2 in langs[i+1:]:
                    yield entry_template(corpus, corpus.files, languages = (l1,l2))
        elif len(corpus.languages) == 2:
            if len(tmxes) != len(corpus.files):
                raise Exception(f"Expected all TMX files.  Check for extra cruft in {corpus.number}: {corpus.files}")
            yield entry_template(corpus, tmxes)
        elif len(corpus.languages) > 2 and len(tmxes) > 1:
            # Multilingual with separate TMXes.  Parse filenames into language codes and gather by language code.
            pairs = {}
            for f in tmxes:
                from_name = parse_language_from_filename(f, corpus.languages)
                if from_name and set(from_name) != corpus.tmx_languages[f]:
                    print(f"TMX languages {corpus.tmx_languages[f]} do not match filename {pair} in corpus {corpus.number}", file=sys.stderr)
                langs = corpus.tmx_languages[f]
                # Alas set is not hashable.
                langs = list(langs)
                langs.sort()
                for i, l1 in enumerate(langs):
                    for l2 in langs[i+1:]:
                        pair = (l1, l2)
                        if pair in pairs:
                            pairs[pair].append(f)
                        else:
                            pairs[pair] = [f]
            for pair, files in pairs.items():
                yield entry_template(corpus, files, languages = pair)
        else:
            raise Exception(f"Unsure what the TMX structure of {corpus.number} {corpus.name} is with {corpus.files}")

def print_mtdata(corpora):
    for r in create_records(corpora):
        print(r)

try:
    corpora = load_metadata()
except FileNotFoundError:
    print("# Download all the JSON files first:")
    print("for ((i=0;i<5000;++i)); do if [ ! -s $i.json ]; then echo wget -O $i.json https://www.elrc-share.eu/repository/export_json/$i/; fi; done |parallel")
    sys.exit(1)
hotfix_metadata(corpora)
to_download = load_files(corpora)
if len(to_download) != 0:
    print("# Download the zip files:")
    for c in to_download:
        print(c.wget())
    sys.exit(2)
hotfix_files(corpora)
print_mtdata(corpora)

# TSV of failures
#with open("../fails.txt") as f:
#   for line in f:
#       line = line.strip()
#       if len(line) == 0:
#           continue
#       num, comment = line.split(' ', maxsplit=1)
#       num = int(num)
#       print(f"{num}\t{corpora[num].info_url}\t{corpora[num].name}\t{comment}")

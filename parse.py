#!/usr/bin/env python
# A voodoo interpreter of ELRC-SHARE.
# ELRC metadata is sequentially numbered.  5000 is higher than their maximum when this was written.
NUM_MAX=5000
import json
import os
import re
import sys
import zipfile

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

class Corpus:
    def __init__(self, number : int, json_data):
        self.number = number
        self.json_data = json_data
        #Feel bad about this, maybe some headword extraction
        self.shortname = str(number)
        # Extract name, preferably in English.
        names = list_if_not(json_data["resourceInfo"]["identificationInfo"]["resourceName"])
        self.name = names[0]["#text"]
        for n in names:
            if n["@lang"] == "en":
                self.name = n["#text"]
        self.processed_name = self.name.endswith("(Processed)")
        self.info_url = json_data["resourceInfo"]["identificationInfo"]["url"]

        # Extract relations.
        self.versions = []
        self.aligned_annotated = []
        self.part_of = []
        self.has_part = []
        for relation in possibly_empty_list(json_data["resourceInfo"], "relationInfo"):
            relation_type = relation["relationType"]
            relation_with = relation["relatedResource"]["targetResourceNameURI"]
            try:
                relation_with = int(relation_with)
            except ValueError as e:
                # WTF
                if relation_with == 'MARCELL Croatian legislative subcorpus':
                    relation_with = 2645
                else:
                    raise e
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
    REQUIRES_POST=set(["NLOD-1.0", "Apache-2.0"])

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
               self.languages.add(l["languageId"])
           linguality = info['lingualityInfo']['lingualityType']
           self.linguality.add(linguality)
           if linguality == "multilingual" and 'multilingualityType' in info['lingualityInfo'] and info['lingualityInfo']['multilingualityType'] in ['other', 'comparable']:
               self.reject(f"multilingualityType is {info['lingualityInfo']['multilingualityType']}")
               return
           

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
       alive_versions = [v for v in corpus.versions if not corpora[v].rejected]
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
    
    corpora[1834].reject("test XML")
    corpora[2654].reject("post-editing training data")
    corpora[4244].reject("Download broken")
    corpora[2606].reject("XLIFF format; TMX is supposed to be available as 2610 but that is not available for download yet and the corpus is too small to bother with an XLIFF parser")
    corpora[2483].reject("Unaligned text file")
    corpora[3860].reject("Available in another format as 3859")
    for i in [3858, 3859, 3860, 3861, 3862, 3864]:
        corpora[i].reject("Same download location as EMEA.")
    corpora[3836].reject("TODO: extract from this non-standard format")
    corpora[2646].reject("TODO: nested zip files, ugh")
    #Multilingual corpus in HEALTH (COVID-19) domain part_1a (v.1.0) when Multilingual corpus in HEALTH (COVID-19) domain part_1a (v.1.05) exists
    for old_health in [3858, 3861, 3862, 3863, 3866, 3867, 3870, 3872]:
        corpora[old_health].reject("Old version")
    
    # Have TMX in a language but not in the metadata
    corpora[416].languages.add("sr")
    corpora[416].languages.add("el")
    
    # Nicer names for multilingual corpora
    for parent, name in [
        (3192, 'antibiotic'),
        (2682, 'EMEA'),
        (3550, 'presscorner_covid'),
        (1134, 'EUIPO_2017'),
        (704, 'EUIPO_list'),
        (2865, 'EU_publications_medical_v2'),
        (3549, "EUR_LEX_covid"),
        (3448, "EC_EUROPA_covid"),
        (3254, "EUROPARL_covid"),
        (2922, "wikipedia_health"),
        (2730, "vaccination"),
    ]:
        combined = corpora[parent].versions + corpora[parent].aligned_annotated + corpora[parent].has_part
        for v in combined:
            corpora[v].shortname = name


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
    if n == 'ELRC_474_Natolin European Centre Dataset (Processed)_VALREP.pdf':
        return False
    return True

def load_files(corpora : List[Corpus]):
    to_download = []
    remaining = [c for c in corpora if c and c.rejected is None]
    for corpus in remaining:
        f = str(corpus.number) + ".zip"
        try:
            with zipfile.ZipFile(f, 'r') as zipped:
                names = zipped.namelist()
            names = [n for n in names if keep_file(n)]
            corpus.files = names
            # Hopefully we didn't delete everything!
            assert len(names) != 0
        except FileNotFoundError:
            to_download.append(corpus)
        except zipfile.BadZipFile:
            print(f"File {f} from {corpus.download} is not a zip file.  Most likely this means the corpus has an open license but ELRC put a click wrap on it for no reason.  Consider adding it to the list of licenses in REQUIRES_POST in the source of this script.", file=sys.stderr)
    return to_download

def hotfix_files(corpora):
    # TMX file fixes: Same TMX in file with two different names
    assert '335-1254.es-pt.tmx' in corpora[1254].files
    corpora[1254].files = ['335-1254.es-pt.tmx']
    # Extra text files alongside tmx
    for index in [1796, 1797]:
        corpora[index].files = [f for f in corpora[index].files if not f.endswith(".txt")]
    # Incorrect language code se, should be sv.  Sorry Sweden, Tilde messed up the metadata for your corpus!  I notified Tilde.
    corpora[417].files = [f for f in corpora[417].files if not f.endswith("-se.tmx")]

def entry_template(corpus : Corpus, inpaths : List[str], shortname = None, languages = None):
    if languages is None:
        languages = corpus.languages
    if shortname is None:
        if corpus.shortname is None:
            raise Exception(f"Need to assign a shortname for {corpus.number} {corpus.name}")
        shortname = corpus.shortname
    cite = "@misc{ELRC-" + shortname + ", title={" + corpus.name.replace("'", "\\'")  + "}, url={" + corpus.info_url + "},}"
    assert len(languages) == 2
    langs = list(languages)
    ret = f"index.add_entry(Entry(langs=('{langs[0]}','{langs[1]}'), name='ELRC_{shortname}', url='{corpus.download}', filename='ELRC_{corpus.number}.zip', in_ext='tmx', in_paths=["
    paths = ["'" + p.replace("'", "\\'") + "'" for p in inpaths]
    ret += ','.join(paths)
    ret += f"], cite='{cite}'))"
    return ret

def nteu(corpus):
    langs = list(corpus.languages)
    langs.sort()
    tiera = langs[0] + "-" + langs[1] + "-a.tmx"
    assert tiera in corpus.files
    tierb = langs[0] + "-" + langs[1] + "-b.tmx"
    assert tierb in corpus.files
    return [entry_template(corpus, [tiera], shortname = "NTEU_TierA"), entry_template(corpus, [tierb], shortname = "NTEU_TierB")]

def parse_language(filename, languages):
    filename = filename.replace("en-GB", "en").replace("de-DE", "de").replace("fr-FR", "fr").replace("it-IT", "it").replace("es-ES", "es").replace("pt-PT", "pt")
    split = re.split('[/_. -]', filename)
    if len(split) < 2:
        raise Exception("Not sure how to parse filename " + filename)
    map639 = {
        "eng" : "en",
        "bul" : "bg",
        "lav" : "lv",
        "ell" : "el",
        "pol" : "pl",
        "ron" : "ro",
        "fra" : "fr",
    }
    for i in range(len(split) - 1):
        if split[i] in languages and split[i+1] in languages:
            return (split[i], split[i+1])
        if split[i] in map639.keys() and split[i+1] in map639.keys() and map639[split[i]] in languages and map639[split[i+1]] in languages:
            return (split[i], split[i+1])
    raise Exception("Could not parse languages out of file name " + filename)

def create_records(corpora: List[Corpus]):
    remaining = [c for c in corpora if c and c.rejected is None]
    records = []
    for corpus in remaining:
        tmxes = [f for f in corpus.files if f.endswith(".tmx")]
        if corpus.name.startswith("Compilation of ") and corpus.name.endswith(" parallel corpora resources used for training of NTEU Machine Translation engines."):
            corpus.shortname = 'NTEU'
            records += nteu(corpus)
        elif len(corpus.files) == 1 and corpus.files[0].endswith(".tmx") and len(corpus.languages) == 2:
            # Sane corpora, thank you!
            records.append(entry_template(corpus, corpus.files))
        elif len(corpus.files) == 1 and corpus.files[0].endswith(".tmx") and len(corpus.languages) > 2:
            # There are 3 multi-lingual corpora that use a single TMX.
            langs = list(corpus.languages)
            for i, l1 in enumerate(langs):
                for l2 in langs[i+1:]:
                    records.append(entry_template(corpus, corpus.files, languages = (l1,l2)))
        elif len(corpus.languages) == 2:
            if len(tmxes) != len(corpus.files):
                raise Exception(f"Expected all TMX files.  Check for extra cruft in {corpus.number}: {corpus.files}")
            records.append(entry_template(corpus, tmxes))
        elif len(corpus.languages) > 2 and len(tmxes) > 1:
            # Multilingual with separate TMXes.  Parse filenames into language codes and gather by language code.
            pairs = {}
            for f in corpus.files:
                pair = parse_language(f, corpus.languages)
                if pair in pairs:
                    pairs[pair].append(f)
                else:
                    pairs[pair] = [f]
            for pair, files in pairs.items():
                records.append(entry_template(corpus, files, languages = pair))
        else:
            raise Exception(f"Unsure what the TMX structure of {corpus.number} {corpus.name} is with {corpus.files}")
    return records
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
print("# Add this to the index file:")
print('\n'.join(create_records(corpora)))
sys.exit(0)

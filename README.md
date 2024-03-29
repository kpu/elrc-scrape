# elrc-scrape
Scrape ELRC-SHARE for corpora.  

As a machine translation person, you just want the all the parallel corpora with the least effort. Something like [OPUS](http://opus.nlpl.eu/).  

There's also parallel data available for download at [ELRC-SHARE](https://elrc-share.eu/) under public domain, public sector information, creative commons, and a few other licenses.  Unfortunately, their site appears to require clicking for each corpus.  And honestly, it's probably not worth your time to download [44 parallel sentences](https://elrc-share.eu/repository/browse/methodological-reconciliation-processed/8fba4be6171411e8b7d400155d0267061a11daf2beeb48cf8834ec9c3278db68/).  

While there is [an official client](https://gitlab.com/ilsp-nlpli-elrc-share/elrc-share-client), it appears to require a login which in turn requires an affiliation with ELRC or a CEF-funded project.  So I made a scraper of sorts.

Here's how to make a TSV of public parallel corpora in ELRC-SHARE:
```bash
# Download JSON files.
for ((i=0;i<5000;++i)); do
  if [ ! -s $i.json ]; then
    echo wget -O $i.json https://www.elrc-share.eu/repository/export_json/$i/
  fi
done |parallel
# Download zip files
./parse.py |parallel
# Generate TSV with l1, l2, num, short_name, name, info, download, post (string for HTTP POST, empty if not required), licenses (space separated), in_paths (tab separated if multiple files)
./parse.py >elrc_share.tsv
```
ELRC uses sequence numbers.  Many of these will yield error 500.  That's expected.  If you don't get a series of 500s at the end, ELRC has more than 5000 records.  Increase the number and edit `NUM_MAX` in `parse.py`

The plan is for all the corpora to be listed in the [mtdata](https://github.com/thammegowda/mtdata) tool for automatic downloading.

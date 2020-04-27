# elrc-scrape
Scrape ELRC-SHARE for corpora.  

As a machine translation person, you just want the all the parallel corpora with the least effort. Something like [OPUS](http://opus.nlpl.eu/).  

There's also parallel data available for download at [ELRC-SHARE](https://elrc-share.eu/) under public domain, public sector information, creative commons, and a few other licenses.  Unfortunately, their site appears to require clicking for each corpus.  And honestly, it's probably not worth your time to download [44 parallel sentences](https://elrc-share.eu/repository/browse/methodological-reconciliation-processed/8fba4be6171411e8b7d400155d0267061a11daf2beeb48cf8834ec9c3278db68/).  

While there is [an official client](https://gitlab.com/ilsp-nlpli-elrc-share/elrc-share-client), it appears to require a login which in return requires an affiliation with ELRC or a CEF-funded project.  

So I made a selenium scraper.  [Shop for the corpora you want](https://elrc-share.eu/repository/search/) using the filters.  When you're done, copy the search URL and provide it as an argument to the scraper.  Remember to quote the URL.  
```bash
./scrape.py "https://elrc-share.eu/repository/search/?q=&selected_facets=licenceFilter_exact%3APublic%20Domain&selected_facets=multilingualityTypeFilter_exact%3AParallel&selected_facets=resourceTypeFilter_exact%3Acorpus"
```
You'll end up with a bunch of hashed directories in the current working directory named after the hash used on the ELRC site.  Each contains `archive.zip` for the corpus and `metadata.txt` with the [short description of the license](https://elrc-share.eu/info/#Licensing_LRs) and the URL of the ELRC landing page.

Don't close Firefox immediately because it's probably still downloading when the script finishes!

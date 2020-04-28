#!/usr/bin/env python3
import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import NoSuchElementException

def setup_driver():
    profile = webdriver.FirefoxProfile();
    profile.set_preference("browser.download.folderList",2)
    profile.set_preference("browser.download.manager.showWhenStarting",False)
    profile.set_preference("browser.helperApps.neverAsk.saveToDisk","application/zip")
    profile.set_preference("general.warnOnAboutConfig", False)
    profile.set_preference("browser.aboutConfig.showWarning", False)
    options = Options()
    options.headless = True
    return webdriver.Firefox(firefox_profile = profile, firefox_options = options)

#https://tarunlalwani.com/post/change-profile-settings-at-runtime-firefox-selenium/
def set_string_preference(driver, name, value):
    driver.execute_script("""
    var prefs = Components.classes["@mozilla.org/preferences-service;1"]
        .getService(Components.interfaces.nsIPrefBranch);
    prefs.setCharPref(arguments[0], arguments[1]);
    """, name, value)

def change_download_directory(driver, to):
    driver.get("about:config")
    set_string_preference(driver, "browser.download.dir", to)


class ResourceLink:
    def __init__(self, href, license):
        self.href = href
        self.license = license
        self.longhash = self.href.split('/')[6]

def parse_page_for_resources(driver):
    ret = [ResourceLink(
            r.find_element_by_css_selector("a:nth-child(2)").get_attribute("href"),
            r.find_element_by_class_name("licence").text)
           for r in driver.find_elements_by_class_name("resourceName")]
    if len(ret) == 0:
        headline = driver.find_element_by_css_selector(".content_box > h3:nth-child(1)").text
        assert headline == "0 Language Resources"
    return ret

#Take a link and extract all search results, including multiple pages.
#Example URL: https://elrc-share.eu/repository/search/?q=&selected_facets=licenceFilter_exact%3APublic%20Domain&selected_facets=multilingualityTypeFilter_exact%3AParallel&selected_facets=resourceTypeFilter_exact%3Acorpus
def list_resources(driver, search_url):
    driver.get(search_url)
    resources = parse_page_for_resources(driver)
    headline = driver.find_element_by_css_selector(".content_box > h3:nth-child(1)").text
    if headline.find("Page") == -1:
        #No pagination
        return resources
    pagination = headline[headline.find("Page")+4:]
    assert pagination[0] == ' '
    assert pagination[-1] == ')'
    pagination = pagination[1:-1].split(' ')
    assert pagination[1] == 'of'
    if pagination[0] != '1':
        raise Exception("Search page URL should start at 1")
    pages = int(pagination[2])
    # We already have page 1.
    for page in range(2, pages + 1):
        driver.get(search_url + "&page=" + str(page))
        resources += parse_page_for_resources(driver)
    return resources

def download_corpus(driver, resource_link):
    longhash = resource_link.longhash
    download = os.getcwd() + "/" + longhash
    if (os.path.exists(download + '/archive.zip')):
        print("Skipping " + download + " since it already exists.")
        return
    change_download_directory(driver, download)
    download_url = "https://elrc-share.eu/repository/download/" + longhash + '/'
    driver.get(download_url)
    header = driver.find_element_by_css_selector("#content > h2:nth-child(2)").text
    if header == "Permission Denied (403)":
        print("Got 403 for downloading " + resource_link.href)
        return
    try:
        element = driver.find_element_by_id("id_licence_agree")
    except(NoSuchElementException):
        print("No download link on " + download_url)
        return
    element.click()
    try:
        os.mkdir(download)
    except(FileExistsError):
        if os.path.exists(download + '/archive.zip'):
            print("Skipping " + download + " since it already exists.")
            return
    with open(download + "/metadata.txt", "w") as f:
        f.write(resource_link.href + "\n" + resource_link.license + "\n")
    element.submit()
    print("Downloading " + download + "/archive.zip")
    while not os.path.exists(download + '/archive.zip.part') and not os.path.exists(download + '/archive.zip'):
        time.sleep(0.5)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Scraper for ELRC-SHARE. Provide a search URL like https://elrc-share.eu/repository/search/?q=&selected_facets=licenceFilter_exact%3APublic%20Domain&selected_facets=multilingualityTypeFilter_exact%3AParallel&selected_facets=resourceTypeFilter_exact%3Acorpus to download all public-domain data.")
        sys.exit(1)
    search_url = sys.argv[1]
    driver = setup_driver()
    for c in list_resources(driver, search_url):
        download_corpus(driver, c)

# Primary function that scrapes all the features from each repository.
# Calls gitfeatures.py which contains many of the individual features.

import json
import gitfeatures as gf
import signal
import numpy as np


class TimeoutException(Exception):   # Custom exception class
    pass


def timeout_handler(signum, frame):   # Custom signal handler
    raise TimeoutException


class Github_Profile:
    """
    Class containing the stats for each Github Profile
    """
    def __init__(self):
        self.user = ''
        self.url = ''
        # metrics
        self.commit_history = []
        self.commits_per_time = 0
        self.n_commits = 0
        self.n_stars = 0
        self.n_forks = 0
        self.test_lines = 0
        self.docstring_lines = 0
        self.comment_lines = 0
        self.readme_lines = 0
        self.code_lines = 0
        self.n_pyfiles = 0
        self.pep8 = {}
        a = ['E1', 'E2', 'E3', 'E4', 'E5', 'E7',
             'E9', 'W1', 'W2', 'W3', 'W5', 'W6']
        for p in a:
            self.pep8[p] = 0


def get_metrics_per_file(item, GProfile):
    """
    Extract metrics from each Python file:
        -comment/code ratio
        -pep8 errors
        -number of code lines and test lines
    """
    r = gf.get_request(item['download_url'])
    if r.ok:
        text = r.text

        # metrics
        GProfile.comment_lines += gf.get_comments(text, '#', '\n')
        GProfile.docstring_lines += gf.get_comments(text, '"""', '"""')
        gf.get_pep8_errs(text, GProfile)

        code_len = len(text.split('\n'))
        GProfile.code_lines += code_len

        # tests
        if item['name'].lower()[:5] == 'test_' and 'assert' in text:  # pytest
            GProfile.test_lines += code_len


def digest_repo(repo_url, GProfile):
    """
    Look through each file and directory, extract metrics from
    each python file. Recursive function.
    """
    r = gf.get_request('%s' % repo_url)
    if r.ok:
        repoItems = json.loads(r.text or r.content)

        signal.signal(signal.SIGALRM, timeout_handler)
        for item in repoItems:
            signal.alarm(10)  # skip file if takes more than 10 seconds

            try:
                if item['type'] == 'file' and item['name'][-3:] == '.py':
                    GProfile.n_pyfiles += 1
                    print(item['download_url'])
                    get_metrics_per_file(item, GProfile)
                elif item['type'] == 'dir':
                    digest_repo(item['url'], GProfile)
            except TimeoutException:
                print('%s timed out, skipping!' % item['download_url'])


def get_features(item, GP):
    """
    Top-level function that scrapes features for each python file
    and stores it in a Github_Profile class.
    """
    contents_url = '%s/contents' % item['url']

    # scrape readme
    gf.get_readme_length(contents_url, GP)

    # scrape file-by-file stats
    digest_repo(contents_url, GP)

    # scrape commit history
    gf.get_repo_commit_history(item, GP)

    # scrape stargazers
    GP.n_stars = item['stargazers_count']

    # scrape forks
    GP.n_forks = item['forks_count']

    return GP


def get_batch_repos(repo_list_dir, output_dir):
    """
    Top-level function that batch-extracts the statistics
    from a collection of repositories.
    """
    proc_repos = np.loadtxt(output_dir, delimiter=',', usecols=[0], dtype='str')
    repos = open(repo_list_dir, 'r').read().splitlines()
    # Change the behavior of SIGALRM
    signal.signal(signal.SIGALRM, timeout_handler)
    for repo in repos:
        if repo in proc_repos:
            print('already scanned %s' % repo)
            continue
        GP = Github_Profile()
        GP.user = repo.split('repos/')[1].split('/')[0]
        r = gf.get_request(repo)
        if r.ok:
            item = json.loads(r.text or r.content)
            signal.alarm(60)
            try:
                if item['fork'] is False:  # for now ignore forks
                    GP = get_features(item, GP)

                    # write each repo->GP to file
                    string = '%s, %d, %d, %d, %d, %d, %d, %d, %f, %d, %d'
                    data = open(output_dir, 'a')
                    data.write(string % (repo, GP.n_pyfiles, GP.code_lines,
                                         GP.comment_lines, GP.docstring_lines,
                                         GP.test_lines, GP.readme_lines,
                                         GP.n_commits, GP.commits_per_time,
                                         GP.n_stars, GP.n_forks))
                    for key in GP.pep8.keys():
                        data.write(', %d' % GP.pep8[key])
                    data.write('\n')
                    data.close()

            except TimeoutException:
                print('%s timed out, skipping!' % repo)
            except:
                print('skipping repo %s' % repo)


def scrape_single_repo(user_repo):
    """
    Top-level function that scrapes the statistics for a single
    Github repository.
    """
    GP = Github_Profile()
    repo = 'https://api.github.com/repos/%s' % user_repo
    GP.user = repo.split('repos/')[1].split('/')[0]
    r = gf.get_request(repo)
    if r.ok:
        item = json.loads(r.text or r.content)
        signal.alarm(60)
        try:
            if item['fork'] is False:  # for now ignore forks
                GP = get_features(item, GP)
        except:
            print('couldnt scrape %s' % repo)
    return GP


if __name__ == '__main__':
    repo_dir = 'repo_data/top_stars_repos_Python.txt'
    output_dir = "repo_data/top_stars_stats_Python.txt"
    get_batch_repos(repo_dir, output_dir)

"""Team-page discovery: follow the homepage's own links, then let Claude read
pages that list people without any team/member markup."""

from types import SimpleNamespace

import pytest

from harvey.agents.scout import Scout


class FakeBrain:
    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    async def think_json(self, prompt, **kw):
        self.prompts.append(prompt)
        return self.reply


def make_scout(pages, reply):
    s = Scout.__new__(Scout)
    s.brain = FakeBrain(reply)
    s._team_llm_calls = 0
    fetched = []

    async def resolve(domain, retries=1):
        return "https://roordink.nl", SimpleNamespace(text=pages["https://roordink.nl"])

    async def fetch(url, **kw):
        fetched.append(url)
        return SimpleNamespace(text=pages[url]) if url in pages else None

    async def learn(*a):
        pass

    s._resolve_base_url, s._fetch, s._learn_pattern_from_page = resolve, fetch, learn
    return s, fetched


@pytest.mark.asyncio
async def test_follows_homepage_team_link_and_reads_plain_text_with_claude():
    pages = {
        "https://roordink.nl": '<a href="/onze-mensen">Onze mensen</a><a href="/ons-werk">Werk</a>',
        "https://roordink.nl/onze-mensen": "<div><p>architect</p><p>Ted Maters</p></div>",
    }
    s, fetched = make_scout(pages, [
        {"first_name": "Ted", "last_name": "Maters", "title": "architect", "decision_maker": True},
        {"first_name": "Ons", "last_name": "team 2", "title": "", "decision_maker": False},
    ])

    people = await s._scrape_team_page("roordink.nl")

    assert fetched == ["https://roordink.nl/onze-mensen"]
    assert "Ted Maters" in s.brain.prompts[0]
    assert people == [{"first_name": "Ted", "last_name": "Maters",
                       "title": "architect", "decision_maker": True}]


@pytest.mark.asyncio
async def test_claude_extraction_is_capped_per_cycle():
    pages = {"https://roordink.nl": '<a href="/team">Team</a>',
             "https://roordink.nl/team": "<p>Ted Maters</p>"}
    s, _ = make_scout(pages, [])
    s._team_llm_calls = 5

    assert await s._scrape_team_page("roordink.nl") == []
    assert s.brain.prompts == []

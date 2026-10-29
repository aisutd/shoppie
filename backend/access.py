"""Access checks shared by bounded discovery and permitted page collection."""

import os
import re
from urllib.parse import unquote, urlsplit
import requests

USER_AGENT = "ShoppieClassroom/1.0 (educational product-page reader)"


def read_public(url, maximum=4_000_000):
    # bounds downloads and never follows an unreviewed redirect
    try:
        with requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=20,
                          allow_redirects=False, stream=True) as response:
            if response.status_code != 200:
                raise ValueError(f"Source returned HTTP {response.status_code}; no retry or bypass")
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > maximum:
                    raise ValueError("Source exceeded the bounded download size")
            return bytes(data)
    except requests.RequestException:
        raise ValueError("Public source request failed or timed out") from None


def robots_permit(text, url):
    # chooses the most specific user-agent group and longest matching path rule
    groups, agents, rules, has_rules = [], [], [], False
    for line in text.splitlines() + ["User-agent: end-of-file"]:
        line = line.split("#", 1)[0].strip()
        if ":" not in line:
            continue
        name, value = (part.strip() for part in line.split(":", 1))
        name = name.lower()
        if name == "user-agent":
            if has_rules:
                groups.append((agents, rules))
                agents, rules = [], []
                has_rules = False
            agents.append(value.lower())
        elif name in {"allow", "disallow"} and agents:
            has_rules = True
            if value:
                rules.append((value, name == "allow"))
    scores = [max([len(agent) for agent in a if agent and agent != "*" and agent in USER_AGENT.lower()] or [0]) for a, r in groups]
    best = max(scores or [0])
    selected = [group for group, score in zip(groups, scores) if score == best and (best or "*" in group[0])]
    path = unquote(urlsplit(url).path or "/")
    if urlsplit(url).query:
        path += "?" + unquote(urlsplit(url).query)
    matches = []
    for agents, rules in selected:
        for pattern, allow in rules:
            end = pattern.endswith("$")
            pattern = unquote(pattern[:-1] if end else pattern)
            expression = "^" + re.escape(pattern).replace(r"\*", ".*") + ("$" if end else "")
            if re.search(expression, path):
                matches.append((len(pattern.replace("*", "")), allow))
    return max(matches)[1] if matches else True


def fetch_robots(origin):
    try:
        with requests.get(origin + "/robots.txt", headers={"User-Agent": USER_AGENT},
                          timeout=10, allow_redirects=False, stream=True) as response:
            if response.status_code == 404:
                return "User-agent: *\nAllow: /"
            if response.status_code != 200:
                raise ValueError(f"Robots request returned HTTP {response.status_code}; access not confirmed")
            data = bytearray()
            for chunk in response.iter_content(65536):
                data.extend(chunk)
                if len(data) > 256_000:
                    raise ValueError("Robots file is too large")
            text = data.decode("utf-8-sig")
            if "<html" in text.lower():
                raise ValueError("Robots request returned HTML; access not confirmed")
            meaningful = "\n".join(line.split("#", 1)[0].strip() for line in text.splitlines()).strip()
            if meaningful and not re.search(r"(?im)^\s*(user-agent|sitemap|allow|disallow)\s*:", meaningful):
                raise ValueError("Robots response was not a usable robots file")
            return text
    except (requests.RequestException, UnicodeError):
        raise ValueError("Robots request failed; access not confirmed") from None


def permitted_page_retailers():
    # enables only retailer page access your team is actually permitted to use
    from backend.settings import setting
    return {value.strip().lower() for value in setting("SHOPPIE_PAGE_RETAILERS").split(",") if value.strip()}

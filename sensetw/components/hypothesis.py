
from sensetw import Card
import re
import requests


def extract_source_type(uri):
    external_keywords = [
        "facebook", "ithome.com.tw", "udn.com", "storm.mg", "cw.com.tw", "cna.com.tw",
        "teema.org.tw"]
    official_keywords = [
        "gov", "gov.tw", "itsa.gov.tw"]
    for k in external_keywords:
        if k in uri:
            return "外部意見"
    for k in official_keywords:
        if k in uri:
            return "政府與研究報告"
    return "其它"


def annotation_to_card(ann):
    title = ann.title
    quote = ann.quote
    source_url = ann.link
    source_type = extract_source_type(ann.uri)
    tags = ann.tags
    hypothesis_id = ann.id
    comments = ["{user}: {text}".format(user=ann.user, text=ann.text)] \
        if ann.text is not None and len(ann.text) > 0 \
        else []

    card = Card(
        title=title, quote=quote, source_url=source_url, source_type=source_type,
        comments=comments, tags=tags,
        hypothesis_id=hypothesis_id
    )

    return card


class Hypothesis:
    """
    A Hypothesis group with annotations on a topic.
    """

    def __init__(self, api_url, api_key, title, url):
        self.api_url = api_url
        self.api_key = api_key
        self.title = title
        self.url = url

    @property
    def group_id(self):
        group_re = re.compile("//sense.tw/groups/(.*?)/")
        r = group_re.search(self.url)
        return r.group(1)

    @property
    def authorization_headers(self):
        return {
            "Authorization": "Bearer {api_key}".format(api_key=self.api_key)
        }

    def group_search_url(self, offset=0, limit=200):
        return self.api_url + "/search?group={group_id}&limit={limit}&offset={offset}".format(
            group_id=self.group_id, limit=limit, offset=offset)

    def _json_to_annotations(self, rows):
        return [Annotation.from_json(data) for data in rows]

    def _search_all_annotations(self, accum, agent, headers, offset=0, limit=200):
        response = agent.get(
            self.group_search_url(offset=offset, limit=limit),
            headers=headers)
        data = response.json()
        accum.extend(data["rows"])
        if len(accum) >= data["total"]:
            return accum
        else:
            return self._search_all_annotations(accum, agent, headers, offset + limit, limit)

    def annotations(self, agent=None):
        """
        Get annotations from the Hypothesis group as Card.
        """
        if agent is None:
            agent = requests
        headers = {}
        headers.update(self.authorization_headers)
        rows = self._search_all_annotations([], agent, headers)
        return [annotation_to_card(ann) for ann in self._json_to_annotations(rows)]


class Annotation(object):

    _fields = ["title", "quote", "uri", "link", "tags", "id",
               "text", "user"]

    def __init__(self, **kwargs):
        for field, value in kwargs.items():
            if field not in self._fields:
                raise TypeError(
                    '"{field}" is not an allowed field'.format(field=field))
        self.__dict__.update(kwargs)

    @classmethod
    def extract_quote(cls, targets):
        if len(targets) == 0:
            return None

        def extract_exact(selectors):
            if len(selectors) == 0:
                return None
            if selectors[0]["type"] == "TextQuoteSelector":
                return selectors[0]["exact"]
            else:
                return extract_exact(selectors[1:])

        if "selector" not in targets[0]:
            return cls.extract_quote(targets[1:])
        exact = extract_exact(targets[0]["selector"])
        if exact is not None:
            return exact
        else:
            return cls.extract_quote(targets[1:])

    @classmethod
    def from_json(cls, data):
        title = data["document"]["title"][0] if "title" in data["document"] else ""
        title = re.sub("[【】\[\]\{\}\|]", " ", title)
        user = data["user"]
        user = re.sub("acct:", "", user)
        user = re.sub("@.*", "", user)
        return Annotation(
            title=title,
            quote=cls.extract_quote(data["target"]),
            uri=data["uri"],
            link=data["links"]["incontext"] if "incontext" in data["links"] else "",
            tags=data["tags"],
            id=data["id"],
            text=data["text"],
            user=user)

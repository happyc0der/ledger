from ledger.attribution import segments, speaker

KW = dict(rep="Rep One", contact_names={"Priya Okafor"}, team_names={"Rep One"}, own_domains={"vireo.com"})


def test_direction_wins():
    assert speaker({"direction": "INCOMING_EMAIL", "author": "Rep One", "text": "x"}, **KW) == ("buyer", "direction")
    assert speaker({"direction": "outbound", "author": "Priya Okafor", "text": "x"}, **KW) == ("rep", "direction")


def test_from_domain():
    assert speaker({"from_addr": "rep@vireo.com", "text": "x"}, **KW)[0] == "rep"
    assert speaker({"from_addr": "priya@acme.com", "text": "x"}, **KW)[0] == "buyer"


def test_auto_reply_is_system():
    assert speaker({"author": "Rep One", "text": "Automatic reply: Priya is no longer with Acme"}, **KW) == ("system", "auto-reply")


def test_author_name_and_unknown():
    assert speaker({"author": "Priya Okafor", "text": "PO next week"}, **KW)[0] == "buyer"
    assert speaker({"author": "Rep One", "text": "Left VM"}, **KW)[0] == "rep"
    assert speaker({"author": "", "text": "Some note"}, **KW)[0] == "unknown"


def test_segments_find_quoted_buyer_words():
    kinds = {k for k, _ in segments('Demo went well. Buyer: "The number is higher than we budgeted." Will follow up.')}
    assert "quoted_buyer" in kinds
    assert any("higher than we budgeted" in s for _, s in segments('Buyer: "The number is higher than we budgeted."'))

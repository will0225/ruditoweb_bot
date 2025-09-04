import re
from decimal import Decimal, ROUND_HALF_UP

CURRENCY_RE = re.compile(r'([€$£])? *([0-9]+(?:[.,][0-9]{1,2})?)')

def parse_amount_to_cents(s):
    """Return (currency_symbol, cents) or (None, None)"""
    if s is None: return (None, None)
    m = CURRENCY_RE.search(s)
    if not m:
        return (None, None)
    cur = m.group(1) or ""
    amt = m.group(2).replace(',', '.')
    # use Decimal to avoid float issues
    d = Decimal(amt).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    cents = int((d * 100).to_integral_value(rounding=ROUND_HALF_UP))
    return (cur, cents)

def parse_price_field(raw_text, context_full_price_cents=None):
    """
    Accepts strings like:
      "750", "750/1000", "€1000", "-25%", "750€", "€750/€1000"
    Returns dict: {currency, full_cents, discounted_cents, needs_review}
    """
    raw = raw_text.strip()
    # percent case
    if raw.endswith('%') or raw.startswith('-'):
        # extract percent number
        p = re.search(r'(\d+(?:[.,]\d+)?)\s*%', raw)
        if p and context_full_price_cents:
            percent = Decimal(p.group(1).replace(',', '.'))
            # compute discounted: full * (100 - percent)/100, rounded
            discounted_cents = int((Decimal(context_full_price_cents) * (100 - percent) / 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            return {'currency': '', 'full_cents': context_full_price_cents, 'discounted_cents': discounted_cents, 'needs_review': False}
        else:
            return {'currency': '', 'full_cents': None, 'discounted_cents': None, 'needs_review': True}

    # slash case A/B
    if '/' in raw:
        parts = raw.split('/')
        left = parts[0].strip()
        right = parts[1].strip()
        cur_l, cents_l = parse_amount_to_cents(left)
        cur_r, cents_r = parse_amount_to_cents(right)
        # assume left = discounted, right = full (per spec)
        discounted = cents_l
        full = cents_r
        currency = cur_l or cur_r or ''
        # swap if discounted > full
        if discounted and full and discounted > full:
            discounted, full = full, discounted
        return {'currency': currency, 'full_cents': full, 'discounted_cents': discounted, 'needs_review': False}

    # single numeric case -> treat as discounted (per earlier plan); full unknown
    cur, cents = parse_amount_to_cents(raw)
    return {'currency': cur or '', 'full_cents': None, 'discounted_cents': cents, 'needs_review': False}

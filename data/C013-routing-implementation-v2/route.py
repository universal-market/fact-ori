"""Offline exact-query C013 preview. Never an answering or release interface.

No fuzzy matching, normalization, negation stripping, models or live I/O.
Inputs are exact frozen bytes. Empty objections is a caller assertion, not proof
that no correction exists. Reviewed routing and release remain separate gates.
"""
import hashlib
import json

# Populated from immutable scope bindings before publication.
PINS = {'data/C013-curation-decision-scope-v1.json': 'f3c219be0e6b417388a77e3f08c8b1e52e0478c26bb53346b69495e6fe107404', 'data/C013-library-candidate-v1/record.json': '99d4409023fb0206a4df89fd0e37b2d8aa0fad7e64d18a1463862bd9da8aa06c', 'data/C013-library-candidate-v1/transformation.json': '39128fe3bcce95ef64640d66489fd2e3a4f142a2c48287156ca9bbc7cb48c150', 'data/C013-exact-review-attached-bundle-v1.json': '1a2be890941cadea384d3601c71bbe4082586587fedca662dace3d8c581e9972', 'data/C013-v1-factfinder-exact-review-v1.json': '59edbe4e87f6056d462b358a359d989efe530a6de4cd8a86dc9f4409f076bbf2', 'data/C013-exact-review-adoption-v1.json': '2a5e52dd77110c4f2b4f7aa0a193a0833571ca662e0a6c53ea271010accb45b6', 'data/C013-reviewed-pending-events-v1.json': '7d9464f5fb353852d599453b990863752a9650c724c8865924e511d3b752169f', 'data/C013-routing-proposal-v2.json': '7d7abaad621318cb1240cb1afd2d2fa2e5a3c7f0afd6aed60bedd4e70d100710', 'data/C013-routing-design-factfinder-review-v1.json': '906f5a91eccd011346ae30075d20117414d565fa0d4db6913bef3d04048fef28', 'data/C013-routing-design-factomaton-recipient-assessment-v1.json': '8c77f0c17efc17ebfb3dd9282aebc601274a920c4145fb47d3f2ed293fc53afa', 'data/C013-reviewed-pending-view-v2.json': '67167689a1ffc079eecbd877187560dc23770f73b796138eec5a0e54c80fda1e', 'data/C013-pending-metadata-revision-v2/scope.json': 'a27ba0026bd525ca81d033df309744adbc9693f5018e56cafe7e2b36eab8c9e0', 'data/C013-pending-metadata-factfinder-review-v2.json': 'eb597cedff26e6e725b2b95cc24605b6d45035ddabcb7870f8542e31fa848804', 'data/C013-pending-metadata-factomaton-recipient-assessment-v2.json': '734a90fa53f5c9f53b811358405b40ec62d91afce62de0e7c7d08267cb055307', 'data/library-inputs.json': 'a55d21f54be5431bbb3eca6b6428e9bc82d3e5bf711289fd8585936d5605d2ae', 'data/curation-events.json': '99e0cd5801ffead8e803ec816701b8363aa549c023fff174b841c1fa1505a43f', 'data/query-catalog.json': 'f8fb5104b3f46f236a2f979a0c12de11698a3985860522fcc023f9d159183b07', 'public/library.json': '563188b309e946ea0f2dfb5e475d12979b281bd62277694b255e6e851b391060', 'data/C013-factfinder-curation-decision-v1.json': 'ca34357c5d63985abefa708a334ec209a70dbb83a6546e5a49815b39d4f56a24', 'data/C013-curation-factomaton-recipient-assessment-v1.json': 'b3461686a3211caba591d24ac4378380dd54eddd93b27b5eada43bfab3374fd3'}
POSITIVE = 'Lightning can strike the same object or location more than once.'
NEGATIVE = 'That literal claim is false: lightning can strike the same object or location more than once.'
REBUTTAL = 'The literal never-twice claim is false: lightning can strike the same object or location more than once.'
ROUTES = {
    'Can lightning strike the same place twice?': ('eligible_positive', 'Yes. ' + POSITIVE),
    'Can lightning strike the same object more than once?': ('eligible_positive', 'Yes. ' + POSITIVE),
    "Can't lightning strike the same place twice?": ('eligible_positive', POSITIVE),
    'Lightning never strikes the same place twice. True?': ('eligible_negative_premise', NEGATIVE),
    'Is it true that lightning cannot strike the same place twice?': ('eligible_negative_premise', NEGATIVE),
    'Lightning never strikes the same place twice, right?': ('eligible_negative_premise', NEGATIVE),
    'Is the claim that lightning never strikes twice false?': ('eligible_rebuttal', REBUTTAL),
}


def preview(query, inputs, *, unresolved_objections):
    """Return a detached proposed response, always withholding the live answer."""
    if type(query) is not str or len(query) > 4096:
        raise ValueError('query must be a bounded string')
    if type(unresolved_objections) is not list or unresolved_objections:
        raise ValueError('current unresolved objections block preview')
    if type(inputs) is not dict or set(inputs) != set(PINS):
        raise ValueError('exact input set required')
    for path, expected in PINS.items():
        value = inputs[path]
        if type(value) is not bytes or hashlib.sha256(value).hexdigest() != expected:
            raise ValueError('input binding mismatch: ' + path)
    classification, response = ROUTES.get(query, ('unmapped', None))
    record = json.loads(inputs['data/C013-library-candidate-v1/record.json'])
    view = json.loads(inputs['data/C013-reviewed-pending-view-v2.json'])['claims'][0]
    return {
        'mode': 'offline_proposal_pending_exact_implementation_review',
        'query': query,
        'classification': classification,
        'proposed_response_after_remaining_gates': response,
        'answer': None,
        'release_authorized': False,
        'record_id': record['id'],
        'record_version': record['version'],
        'record_sha256': '9f8ac32f0cb68e2ba05cdd04c8dc9af49943135c284952dcc1abdaf1836835ee',
        'limitations': view['limitations'],
        'historical_draft_metadata': view['historical_draft_metadata'],
        'source_dependence_groups': view['source_dependence_groups'],
        'inference': record.get('inference'),
        'scope': record['scope'],
        'excluded_scopes': record['exclusions'],
        'input_raw_sha256': dict(PINS),
        'objection_check': 'caller reports empty; not authenticated or automatically refreshed',
    }

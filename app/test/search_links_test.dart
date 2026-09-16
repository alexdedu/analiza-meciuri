import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/search_links.dart';

/// Adresele de cautare se construiesc din nume scrise de mana, deci trebuie sa
/// reziste la spatii in plus, diacritice si campuri goale.
void main() {
  test('adresa este o cautare Google', () {
    final u = buildSearchUrl('AC Milan', 'Benfica', SearchKind.general);
    expect(u.scheme, 'https');
    expect(u.host, 'www.google.com');
    expect(u.path, '/search');
  });

  test('interogarea contine ambele echipe', () {
    final u = buildSearchUrl('AC Milan', 'Benfica', SearchKind.general);
    expect(u.queryParameters['q'], 'AC Milan vs Benfica');
  });

  test('fiecare tip de cautare adauga alte cuvinte', () {
    final stats = buildSearchUrl('AC Milan', 'Benfica', SearchKind.statistici);
    final ponturi = buildSearchUrl('AC Milan', 'Benfica', SearchKind.ponturi);
    expect(stats.queryParameters['q'], contains('statistici'));
    expect(ponturi.queryParameters['q'], contains('ponturi'));
    expect(stats.queryParameters['q'], isNot(equals(ponturi.queryParameters['q'])));
  });

  test('spatiile in plus sunt taiate', () {
    final u = buildSearchUrl('  AC Milan  ', '  Benfica ', SearchKind.general);
    expect(u.queryParameters['q'], 'AC Milan vs Benfica');
  });

  test('o singura echipa scrisa nu produce un "vs" orfan', () {
    final u = buildSearchUrl('AC Milan', '', SearchKind.general);
    expect(u.queryParameters['q'], 'AC Milan');
    expect(u.queryParameters['q'], isNot(contains('vs')));
  });

  test('diacriticele si caracterele speciale sunt codate corect', () {
    final u = buildSearchUrl('Universitatea Craiova', 'FCSB & Co', SearchKind.general);
    // Valoarea decodata ramane intacta, iar adresa nu se rupe la & sau spatii.
    expect(u.queryParameters['q'], 'Universitatea Craiova vs FCSB & Co');
    expect(u.toString(), contains('%26'));
  });

  test('stim cand nu avem ce cauta', () {
    expect(canSearch('', ''), isFalse);
    expect(canSearch('   ', '  '), isFalse);
    expect(canSearch('Benfica', ''), isTrue);
  });
}

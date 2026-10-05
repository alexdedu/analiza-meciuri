import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/notificari.dart';

/// Notificarile trebuie sa vina o singura data pentru acelasi lucru, sa nu
/// inunde telefonul, si sa nu anunte miscari prea mici ca sa conteze.
Map<String, dynamic> fisier({
  String? biletData = '2026-10-08',
  List<Map<String, dynamic>> picks = const [],
}) =>
    {
      if (biletData != null)
        'ticket_of_the_day': {
          'date': biletData,
          'legs': [{}, {}, {}, {}, {}],
          'combined_odds': 11.4,
          'combined_probability': 0.098,
          'odds_estimated': true,
        },
      'recommended_matches': [
        {'match_id': 'M1', 'home': 'Mainz', 'away': 'Leverkusen', 'picks': picks},
      ],
    };

Map<String, dynamic> pick(String market, double cota, double? miscare) => {
      'market': market,
      'market_label': 'Peste 2.5 goluri',
      'odds': cota,
      'odds_movement': miscare,
    };

const gol = StareNotificari(ultimulBilet: null, scaderiAnuntate: {});

void main() {
  test('anunta biletul zilei o singura data', () {
    final (prima, stare) = decide(fisier(), gol);
    expect(prima.where((n) => n.titlu == 'Biletul zilei e gata'), hasLength(1));
    expect(prima.first.text, contains('5 selecții'));
    expect(prima.first.text, contains('11.40'));

    final (aDoua, _) = decide(fisier(), stare);
    expect(aDoua.where((n) => n.titlu == 'Biletul zilei e gata'), isEmpty,
        reason: 'acelasi bilet a fost anuntat de doua ori');
  });

  test('un bilet nou, din alta zi, se anunta din nou', () {
    final (_, stare) = decide(fisier(biletData: '2026-10-08'), gol);
    final (n, _) = decide(fisier(biletData: '2026-10-09'), stare);
    expect(n.where((x) => x.titlu == 'Biletul zilei e gata'), hasLength(1));
  });

  test('anunta cota care scade, cu pretul vechi si cel nou', () {
    final (n, _) = decide(
        fisier(biletData: null, picks: [pick('over25', 1.50, 0.06)]), gol);
    expect(n, hasLength(1));
    expect(n.first.titlu, contains('Mainz – Leverkusen'));
    expect(n.first.text, contains('1.59 → 1.50'));
    expect(n.first.text, contains('pune-o acum'));
  });

  test('o scadere mica nu merita o notificare', () {
    final (n, _) = decide(
        fisier(biletData: null, picks: [pick('over25', 1.50, 0.02)]), gol);
    expect(n, isEmpty);
  });

  test('aceeasi scadere nu se anunta de doua ori', () {
    final f = fisier(biletData: null, picks: [pick('over25', 1.50, 0.06)]);
    final (_, stare) = decide(f, gol);
    final (n, _) = decide(f, stare);
    expect(n, isEmpty);
  });

  test('nu inunda telefonul: cel mult trei cote odata', () {
    final picks = [
      for (var i = 0; i < 6; i++) pick('m$i', 1.50, 0.05 + i / 100),
    ];
    final (n, _) = decide(fisier(biletData: null, picks: picks), gol);
    expect(n, hasLength(maximScaderi));
    // Cele mai mari scaderi au intaietate.
    expect(n.first.text, contains('-10%'));
  });

  test('selectiile care au disparut din fisier sunt uitate', () {
    final (_, stare) = decide(
        fisier(biletData: null, picks: [pick('over25', 1.50, 0.06)]), gol);
    expect(stare.scaderiAnuntate, contains('M1|over25'));
    final (_, dupa) = decide(fisier(biletData: null, picks: []), stare);
    expect(dupa.scaderiAnuntate, isEmpty);
  });
}

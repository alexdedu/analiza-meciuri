import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/counts_card.dart';
import 'package:football_predictor/models.dart';

/// Cornerele si cartonasele sunt piete pe care modelul le stapaneste inegal.
/// Cardul trebuie sa spuna asta, altfel un procent slab arata la fel de sigur
/// ca unul bun.
CountsMarket piata({Map<String, double>? castigator}) => CountsMarket(
      expectedHome: 5.4,
      expectedAway: 3.8,
      expectedTotal: 9.2,
      total: const [
        CountLine(line: 8.5, over: 0.56, under: 0.44),
        CountLine(line: 9.5, over: 0.43, under: 0.57),
      ],
      home: const [CountLine(line: 4.5, over: 0.63)],
      away: const [CountLine(line: 4.5, over: 0.41)],
      winner: castigator,
      sample: 1131,
    );

Future<void> pump(WidgetTester tester, CountsKind kind,
        {Map<String, double>? castigator}) =>
    tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: CountsCard(
            market: piata(castigator: castigator),
            kind: kind,
            home: 'Arsenal',
            away: 'Chelsea',
          ),
        ),
      ),
    ));

void main() {
  testWidgets('arata asteptarile si liniile de total', (tester) async {
    await pump(tester, CountsKind.corners);
    expect(find.textContaining('5.4 pentru Arsenal'), findsOneWidget);
    expect(find.textContaining('peste 56% · sub 44%'), findsOneWidget);
  });

  testWidgets('spune ca totalul de cornere nu bate media campionatului',
      (tester) async {
    await pump(tester, CountsKind.corners);
    expect(find.text('cât media campionatului'), findsOneWidget);
    expect(find.textContaining('nu s-a dovedit mai bun decât media'),
        findsOneWidget);
  });

  testWidgets('la cartonase spune ca arbitrul nu intra in model',
      (tester) async {
    await pump(tester, CountsKind.cards);
    expect(find.textContaining('arbitrul nu intră în model'), findsOneWidget);
    expect(find.text('Cartonașe'), findsOneWidget);
  });

  testWidgets('avertizeaza ca nu intra in selectiile automate', (tester) async {
    await pump(tester, CountsKind.corners);
    expect(find.textContaining('nu intră în selecțiile automate'), findsOneWidget);
  });

  testWidgets('cine da mai multe apare doar cand exista', (tester) async {
    await pump(tester, CountsKind.cards);
    expect(find.text('Cine dă mai multe'), findsNothing);

    await pump(tester, CountsKind.corners,
        castigator: const {'home': 0.65, 'draw': 0.12, 'away': 0.23});
    expect(find.text('Cine dă mai multe'), findsOneWidget);
    expect(find.textContaining('Arsenal 65%'), findsOneWidget);
  });

  test('sectiunea lipseste cand sursa nu are datele', () {
    expect(ExtraMarkets.fromJson(null), isNull);
    expect(ExtraMarkets.fromJson(const {}), isNull);
  });
}

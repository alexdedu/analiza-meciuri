import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/models.dart';
import 'package:football_predictor/recommendations_card.dart';

/// Sectiunea de selectii trebuie sa arate mereu si rata istorica, nu doar
/// procentul modelului: altfel ar parea o promisiune.
Recommendation rec({
  String matchId = 'M1',
  double probability = 0.72,
  double odds = 1.38,
  double marketProbability = 0.70,
  String band = '70-80%',
  double hitRate = 0.753,
}) =>
    Recommendation(
      matchId: matchId,
      leagueName: 'Premier League',
      date: '2026-09-20',
      time: '17:00',
      home: 'Arsenal',
      away: 'Lille',
      marketLabel: 'Victorie Arsenal',
      probability: probability,
      odds: odds,
      marketProbability: marketProbability,
      band: band,
      historicalHitRate: hitRate,
    );

Future<void> pump(WidgetTester tester, List<Recommendation> list) =>
    tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: RecommendationsCard(recommendations: list, onTap: (_) {}),
        ),
      ),
    ));

void main() {
  testWidgets('afiseaza pariul, procentul si cota', (tester) async {
    await pump(tester, [rec()]);
    expect(find.text('Victorie Arsenal'), findsOneWidget);
    expect(find.text('72%'), findsOneWidget);
    expect(find.textContaining('Cotă 1.38'), findsOneWidget);
  });

  testWidgets('arata rata istorica a benzii, nu doar procentul modelului',
      (tester) async {
    await pump(tester, [rec()]);
    expect(find.textContaining('istoric la 70-80%: 75% reușite'), findsOneWidget);
  });

  testWidgets('spune explicit ca nu sunt pariuri sigure', (tester) async {
    await pump(tester, [rec()]);
    expect(find.textContaining('Nu sunt pariuri sigure'), findsOneWidget);
    expect(find.textContaining('31,5%'), findsOneWidget);
  });

  testWidgets('lista goala explica de ce, nu ramane muta', (tester) async {
    await pump(tester, []);
    expect(find.textContaining('Niciun meci nu trece filtrele'), findsOneWidget);
    expect(find.textContaining('date solide'), findsOneWidget);
  });

  testWidgets('apasarea duce catre meciul corect', (tester) async {
    String? apasat;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: RecommendationsCard(
          recommendations: [rec(matchId: 'MECI_42')],
          onTap: (id) => apasat = id,
        ),
      ),
    ));
    await tester.tap(find.text('Victorie Arsenal'));
    expect(apasat, 'MECI_42');
  });
}

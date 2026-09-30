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
  String band = 'sub piață',
  double hitRate = 0.653,
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

  testWidgets('arata rata istorica a nivelului, nu doar procentul modelului',
      (tester) async {
    await pump(tester, [rec()]);
    expect(find.textContaining('model sub piață, unde istoric ies 65%'),
        findsOneWidget);
  });

  testWidgets('spune unde iese si unde nu iese randamentul', (tester) async {
    await pump(tester, [rec()]);
    // Cifra care conteaza: la cota medie randamentul masurat e negativ.
    expect(find.textContaining('64,3% reușite'), findsOneWidget);
    expect(find.textContaining('−2,3%'), findsOneWidget);
  });

  testWidgets('cotele mici nu mai au ce cauta in selectii', (tester) async {
    // Regula cere cota de cel putin 1.45; textul trebuie sa spuna asta.
    await pump(tester, [rec()]);
    expect(find.textContaining('cota trece de 1.45'), findsOneWidget);
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

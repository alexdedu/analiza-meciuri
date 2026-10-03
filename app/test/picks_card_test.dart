import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/models.dart';
import 'package:football_predictor/picks_card.dart';

/// Sectiunea trebuie sa arate, la acelasi meci, toate pietele care trec
/// filtrele -- si sa spuna limpede care au cota adevarata si care nu.
MatchPick pick({
  String family = '1x2',
  String market = 'home',
  String label = 'Victorie Arsenal',
  double probability = 0.62,
  double? odds = 1.62,
  double fairOdds = 1.61,
  double hitRate = 0.653,
}) =>
    MatchPick(
      family: family,
      market: market,
      marketLabel: label,
      probability: probability,
      odds: odds,
      fairOdds: fairOdds,
      historicalHitRate: hitRate,
      band: 'sub piață',
    );

RecommendedMatch meci({List<MatchPick>? picks, String id = 'M1'}) =>
    RecommendedMatch(
      matchId: id,
      leagueName: 'Premier League',
      date: '2026-10-10',
      time: '17:00',
      home: 'Arsenal',
      away: 'Leeds',
      picks: picks ?? [pick()],
    );

Future<void> pump(WidgetTester tester, List<RecommendedMatch> matches,
        {CountsRecord? record}) =>
    tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: SingleChildScrollView(
          child: PicksCard(
              matches: matches, countsRecord: record, onTap: (_) {}),
        ),
      ),
    ));

void main() {
  testWidgets('arata toate pietele aceluiasi meci', (tester) async {
    await pump(tester, [
      meci(picks: [
        pick(),
        pick(family: 'goluri', market: 'over25', label: 'Peste 2.5 goluri',
            probability: 0.61, odds: 1.49),
        pick(family: 'cornere', market: 'corners_home_over_4.5',
            label: 'Arsenal peste 4.5 cornere', probability: 0.66,
            odds: null, fairOdds: 1.52, hitRate: 0.642),
      ]),
    ]);

    expect(find.text('Arsenal – Leeds'), findsOneWidget);
    expect(find.text('Victorie Arsenal'), findsOneWidget);
    expect(find.text('Peste 2.5 goluri'), findsOneWidget);
    expect(find.text('Arsenal peste 4.5 cornere'), findsOneWidget);
    // Etichetele scurte ale pietelor.
    expect(find.text('REZ'), findsOneWidget);
    expect(find.text('GOL'), findsOneWidget);
    expect(find.text('CRN'), findsOneWidget);
  });

  testWidgets('cota adevarata si cota corecta se scriu diferit', (tester) async {
    await pump(tester, [
      meci(picks: [
        pick(),
        pick(family: 'cartonașe', market: 'cards_total_over_3.5',
            label: 'peste 3.5 cartonașe în meci', probability: 0.63,
            odds: null, fairOdds: 1.58, hitRate: 0.637),
      ]),
    ]);

    expect(find.textContaining('cotă 1.62'), findsOneWidget);
    expect(find.textContaining('cotă corectă 1.58'), findsOneWidget);
  });

  testWidgets('lista goala spune ce filtre trebuie trecute', (tester) async {
    await pump(tester, []);
    expect(find.textContaining('cotă de cel puțin 1.45'), findsOneWidget);
  });

  testWidgets('bilantul pe cornere apare doar cand s-a verificat ceva',
      (tester) async {
    await pump(tester, [meci()],
        record: const CountsRecord(
            total: 6, resolved: 0, pending: 6, hits: 0,
            hitRate: null, expected: 0.65));
    expect(find.textContaining('Cornere și cartonașe până acum'), findsNothing);

    await pump(tester, [meci()],
        record: const CountsRecord(
            total: 9, resolved: 6, pending: 3, hits: 4,
            hitRate: 0.667, expected: 0.65));
    expect(find.textContaining('4 din 6'), findsOneWidget);
    expect(find.textContaining('promis 65%'), findsOneWidget);
  });

  testWidgets('apasarea duce catre meciul corect', (tester) async {
    String? apasat;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: PicksCard(
          matches: [meci(id: 'MECI_9')],
          countsRecord: null,
          onTap: (id) => apasat = id,
        ),
      ),
    ));
    await tester.tap(find.text('Victorie Arsenal'));
    expect(apasat, 'MECI_9');
  });

  testWidgets('spune unde exista cote si unde nu', (tester) async {
    await pump(tester, [meci()]);
    expect(find.textContaining('La cornere și cartonașe nu există cote'),
        findsOneWidget);
    expect(find.textContaining('64,3% reușite'), findsOneWidget);
  });
}

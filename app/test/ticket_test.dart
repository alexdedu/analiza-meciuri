import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/models.dart';
import 'package:football_predictor/ticket.dart';

/// Biletul trebuie sa arate dintr-o privire cota si sansa, sa duca la fiecare
/// meci, si sa spuna limpede cand cota e estimata.
TicketLeg leg({
  String matchId = 'M1',
  String family = '1x2',
  String home = 'Montenegro',
  String away = 'Armenia',
  String label = 'Victorie Montenegro',
  double probability = 0.60,
  double? odds = 1.60,
  bool? won,
}) =>
    TicketLeg(
      matchId: matchId,
      leagueName: 'Nations League',
      date: '2026-10-05',
      time: '18:00',
      home: home,
      away: away,
      family: family,
      marketLabel: label,
      probability: probability,
      odds: odds,
      fairOdds: double.parse((1 / probability).toStringAsFixed(2)),
      historicalHitRate: 0.65,
      won: won,
    );

Ticket bilet({List<TicketLeg>? legs, bool estimated = true, bool? won}) => Ticket(
      date: '2026-10-04',
      legs: legs ??
          [
            leg(),
            leg(matchId: 'M2', family: 'cornere', home: 'Casa Pia',
                away: 'Santa Clara', label: 'Casa Pia peste 3.5 cornere',
                probability: 0.64, odds: null),
          ],
      combinedProbability: 0.384,
      expectedHitRate: 0.42,
      combinedOdds: 2.50,
      oddsEstimated: estimated,
      won: won,
    );

void main() {
  testWidgets('cardul arata cota, sansa si numarul de selectii', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: TicketCard(ticket: bilet(), onOpen: () {})),
    ));
    expect(find.text('Biletul zilei'), findsOneWidget);
    expect(find.text('2.50'), findsOneWidget);
    expect(find.text('38%'), findsOneWidget);
    expect(find.text('cotă estimată'), findsOneWidget);
  });

  testWidgets('cand toate cotele sunt reale, nu scrie estimata', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
          body: TicketCard(ticket: bilet(estimated: false), onOpen: () {})),
    ));
    expect(find.text('cotă totală'), findsOneWidget);
    expect(find.text('cotă estimată'), findsNothing);
  });

  testWidgets('apasarea cardului deschide biletul', (tester) async {
    var deschis = false;
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
          body: TicketCard(ticket: bilet(), onOpen: () => deschis = true)),
    ));
    await tester.tap(find.text('Biletul zilei'));
    expect(deschis, isTrue);
  });

  testWidgets('ecranul biletului duce la fiecare meci', (tester) async {
    String? deschis;
    await tester.pumpWidget(MaterialApp(
      home: TicketScreen(
        ticket: bilet(),
        record: null,
        onOpenMatch: (_, id) => deschis = id,
      ),
    ));
    expect(find.text('Montenegro – Armenia'), findsOneWidget);
    expect(find.text('Casa Pia – Santa Clara'), findsOneWidget);

    await tester.tap(find.text('Casa Pia – Santa Clara'));
    expect(deschis, 'M2');
  });

  testWidgets('spune ca sansele se inmultesc', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: TicketScreen(ticket: bilet(), record: null, onOpenMatch: (_, __) {}),
    ));
    expect(find.textContaining('Șansele se înmulțesc'), findsOneWidget);
    expect(find.textContaining('meciuri diferite'), findsOneWidget);
  });

  testWidgets('verdictul apare pe card dupa ce s-a jucat', (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(body: TicketCard(ticket: bilet(won: true), onOpen: () {})),
    ));
    expect(find.text('CÂȘTIGAT'), findsOneWidget);
  });

  testWidgets('bilantul biletelor apare doar cand exista rezultate',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: TicketScreen(
        ticket: bilet(),
        record: const TicketRecord(total: 5, resolved: 4, won: 1, expected: 0.2),
        onOpenMatch: (_, __) {},
      ),
    ));
    await tester.scrollUntilVisible(find.textContaining('1 câștigate din 4'), 200);
    expect(find.textContaining('1 câștigate din 4'), findsOneWidget);
  });

  testWidgets('cand nu iese bilet, spune de ce si de cand se poate',
      (tester) async {
    await tester.pumpWidget(MaterialApp(
      home: Scaffold(
        body: TicketUnavailableCard(
          info: TicketUnavailable(
            maxOdds: 5.27,
            legsAvailable: 4,
            minOdds: 10,
            days: 3,
            nextPossible: DateTime(2026, 10, 7),
          ),
        ),
      ),
    ));
    expect(find.textContaining('cel mult la 5.27'), findsOneWidget);
    expect(find.textContaining('Primul bilet posibil: 07.10'), findsOneWidget);
  });

  test('un bilet fara picioare nu se transforma in obiect', () {
    expect(Ticket.fromJson(null), isNull);
    expect(Ticket.fromJson(const {'legs': []}), isNull);
  });
}

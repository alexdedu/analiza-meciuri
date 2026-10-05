import 'dart:convert';

import 'package:flutter/widgets.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';
import 'package:workmanager/workmanager.dart';

import 'config.dart';

/// Notificarile: biletul zilei, si selectiile a caror cota incepe sa scada.
///
/// De ce conteaza a doua: masurat pe 3.695 de selectii, cand cota scade,
/// valoarea era in pretul de la inceput (+4,5% la deschidere fata de -3% la
/// inchidere). Cine afla tarziu, prinde pretul prost.
///
/// Telefonul verifica singur fisierul de predictii, de cateva ori pe zi, fara
/// server si fara cont: e acelasi fisier pe care il citeste si aplicatia.

const _sarcina = 'verifica-predictii';
const _cheieActive = 'notificari_active';
const _cheieBilet = 'notificari_ultimul_bilet';
const _cheieScaderi = 'notificari_scaderi_anuntate';

/// Pragul pentru "pune acum". Mai mare decat cel din aplicatie (2%): o
/// notificare trebuie sa merite intreruperea.
const pragScadere = 0.04;

/// Cate notificari despre cote, cel mult, la o verificare.
const maximScaderi = 3;

/// O notificare de aratat.
class Notificare {
  const Notificare({required this.id, required this.titlu, required this.text});

  final int id;
  final String titlu;
  final String text;
}

/// Ce s-a anuntat deja, ca sa nu se repete.
class StareNotificari {
  const StareNotificari({required this.ultimulBilet, required this.scaderiAnuntate});

  final String? ultimulBilet;
  final Set<String> scaderiAnuntate;
}

String _pct(double v) => '${(v * 100).toStringAsFixed(0)}%';

/// Ce trebuie anuntat, din fisierul de predictii si ce s-a anuntat deja.
///
/// Functie pura, fara retea si fara telefon, ca sa se poata verifica in teste.
(List<Notificare>, StareNotificari) decide(
    Map<String, dynamic> date, StareNotificari stare) {
  final notificari = <Notificare>[];
  var ultimulBilet = stare.ultimulBilet;

  final bilet = date['ticket_of_the_day'] as Map<String, dynamic>?;
  if (bilet != null && bilet['date'] != stare.ultimulBilet) {
    final picioare = (bilet['legs'] as List<dynamic>?) ?? [];
    final cota = (bilet['combined_odds'] as num?)?.toDouble() ?? 0;
    final sansa = (bilet['combined_probability'] as num?)?.toDouble() ?? 0;
    final estimata = (bilet['odds_estimated'] as bool?) ?? false;
    notificari.add(Notificare(
      id: 1,
      titlu: 'Biletul zilei e gata',
      text: '${picioare.length} selecții · cotă ${cota.toStringAsFixed(2)}'
          '${estimata ? ' (estimată)' : ''} · șansă ${_pct(sansa)}',
    ));
    ultimulBilet = bilet['date'] as String?;
  }

  // Cotele in scadere, din selectiile recomandate.
  final vazute = <String>{};
  final scaderi = <(String, double, Notificare)>[];
  for (final m in (date['recommended_matches'] as List<dynamic>?) ?? []) {
    final meci = m as Map<String, dynamic>;
    for (final p in (meci['picks'] as List<dynamic>?) ?? []) {
      final pick = p as Map<String, dynamic>;
      final cheie = '${meci['match_id']}|${pick['market']}';
      vazute.add(cheie);
      final miscare = (pick['odds_movement'] as num?)?.toDouble();
      final cota = (pick['odds'] as num?)?.toDouble();
      if (miscare == null || cota == null || miscare < pragScadere) continue;
      if (stare.scaderiAnuntate.contains(cheie)) continue;
      final inainte = cota * (1 + miscare);
      scaderi.add((
        cheie,
        miscare,
        Notificare(
          id: 100 + cheie.hashCode.abs() % 100000,
          titlu: '${meci['home']} – ${meci['away']}: cota scade',
          text: '${pick['market_label']}: ${inainte.toStringAsFixed(2)} → '
              '${cota.toStringAsFixed(2)} (-${_pct(miscare)}). Valoarea e la '
              'început — dacă o vrei, pune-o acum.',
        ),
      ));
    }
  }
  // Cele mai mari scaderi intai, si nu mai mult de cateva odata.
  scaderi.sort((a, b) => b.$2.compareTo(a.$2));
  final anuntate = {...stare.scaderiAnuntate};
  for (final (cheie, _, notificare) in scaderi.take(maximScaderi)) {
    notificari.add(notificare);
    anuntate.add(cheie);
  }

  // Uitam selectiile care nu mai sunt in fisier, ca lista sa nu creasca la
  // nesfarsit -- un meci jucat nu mai are de ce sa fie tinut minte.
  anuntate.retainAll(vazute);

  return (
    notificari,
    StareNotificari(ultimulBilet: ultimulBilet, scaderiAnuntate: anuntate),
  );
}

final _plugin = FlutterLocalNotificationsPlugin();

const _detalii = NotificationDetails(
  android: AndroidNotificationDetails(
    'selectii',
    'Selecții și bilete',
    channelDescription: 'Biletul zilei și cotele care încep să scadă',
    importance: Importance.high,
    priority: Priority.high,
  ),
);

Future<void> _initPlugin() async {
  await _plugin.initialize(
    settings: const InitializationSettings(
      android: AndroidInitializationSettings('@mipmap/ic_launcher'),
    ),
  );
}

/// Ce face telefonul in fundal: citeste fisierul, decide, anunta.
Future<void> verificaSiAnunta() async {
  final prefs = await SharedPreferences.getInstance();
  if (!(prefs.getBool(_cheieActive) ?? true)) return;
  if (predictionsUrl.isEmpty) return;

  final raspuns = await http
      .get(Uri.parse(predictionsUrl))
      .timeout(const Duration(seconds: 20));
  if (raspuns.statusCode != 200) return;
  final date = jsonDecode(utf8.decode(raspuns.bodyBytes)) as Map<String, dynamic>;

  final stare = StareNotificari(
    ultimulBilet: prefs.getString(_cheieBilet),
    scaderiAnuntate: (prefs.getStringList(_cheieScaderi) ?? []).toSet(),
  );
  final (notificari, nouaStare) = decide(date, stare);

  if (notificari.isNotEmpty) {
    await _initPlugin();
    for (final n in notificari) {
      await _plugin.show(
          id: n.id, title: n.titlu, body: n.text, notificationDetails: _detalii);
    }
  }

  if (nouaStare.ultimulBilet != null) {
    await prefs.setString(_cheieBilet, nouaStare.ultimulBilet!);
  }
  await prefs.setStringList(_cheieScaderi, nouaStare.scaderiAnuntate.toList());
}

/// Punctul de intrare al sarcinii din fundal. Ruleaza fara aplicatie
/// deschisa, deci nu poate folosi nimic din interfata.
@pragma('vm:entry-point')
void callbackDispatcher() {
  Workmanager().executeTask((task, _) async {
    try {
      await verificaSiAnunta();
    } catch (_) {
      // O verificare esuata (fara internet, de pilda) nu e o problema: vine
      // urmatoarea peste doua ore.
    }
    return true;
  });
}

/// Porneste verificarile periodice si cere permisiunea de notificare.
Future<void> pornesteNotificari() async {
  await _initPlugin();
  await _plugin
      .resolvePlatformSpecificImplementation<
          AndroidFlutterLocalNotificationsPlugin>()
      ?.requestNotificationsPermission();

  await Workmanager().initialize(callbackDispatcher);
  await Workmanager().registerPeriodicTask(
    _sarcina,
    _sarcina,
    // Fisierul se actualizeaza de patru ori pe zi; la doua ore prindem orice
    // schimbare la timp, fara sa consumam bateria degeaba.
    frequency: const Duration(hours: 2),
    constraints: Constraints(networkType: NetworkType.connected),
    existingWorkPolicy: ExistingPeriodicWorkPolicy.keep,
  );
}

Future<bool> notificariActive() async =>
    (await SharedPreferences.getInstance()).getBool(_cheieActive) ?? true;

Future<void> seteazaNotificari(bool active) async {
  final prefs = await SharedPreferences.getInstance();
  await prefs.setBool(_cheieActive, active);
}

/// Pentru buton: aplicatia e deschisa, verificam pe loc, nu peste doua ore.
Future<void> verificaAcum() async {
  WidgetsFlutterBinding.ensureInitialized();
  await verificaSiAnunta();
}

import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:football_predictor/repository.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Verifica lantul de rezerva: internet -> ultima descarcare -> fisier inclus.
/// Fara asta, o pana de retea ar lasa aplicatia cu ecranul gol.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  late String validJson;

  setUpAll(() async {
    validJson = await rootBundle.loadString('assets/predictions.json');
  });

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('fara URL configurat, foloseste fisierul din aplicatie', () async {
    final result = await PredictionRepository(url: '').load();
    expect(result.source, DataSource.bundled);
    expect(result.bundle.matches, isNotEmpty);
  });

  test('cu URL valid, descarca de pe internet', () async {
    final client = MockClient((_) async => http.Response.bytes(
          utf8.encode(validJson),
          200,
          headers: {'content-type': 'application/json; charset=utf-8'},
        ));
    final result =
        await PredictionRepository(client: client, url: 'https://exemplu/p.json').load();
    expect(result.source, DataSource.remote);
  });

  test('descarcarea reusita se salveaza pentru data viitoare', () async {
    final client = MockClient((_) async => http.Response.bytes(utf8.encode(validJson), 200));
    await PredictionRepository(client: client, url: 'https://exemplu/p.json').load();

    // A doua incercare: serverul cade, dar avem copia salvata.
    final failing = MockClient((_) async => throw const SocketExceptionStub());
    final result =
        await PredictionRepository(client: failing, url: 'https://exemplu/p.json').load();
    expect(result.source, DataSource.cache);
    expect(result.bundle.matches, isNotEmpty);
  });

  test('fara internet si fara copie salvata, cade pe fisierul din aplicatie', () async {
    final failing = MockClient((_) async => throw const SocketExceptionStub());
    final result =
        await PredictionRepository(client: failing, url: 'https://exemplu/p.json').load();
    expect(result.source, DataSource.bundled);
    expect(result.bundle.matches, isNotEmpty);
  });

  test('un raspuns 404 nu strica datele existente', () async {
    final notFound = MockClient((_) async => http.Response('nu exista', 404));
    final result =
        await PredictionRepository(client: notFound, url: 'https://exemplu/p.json').load();
    expect(result.source, DataSource.bundled);
  });

  test('un raspuns corupt nu ajunge in memoria telefonului', () async {
    final broken = MockClient((_) async => http.Response('{asta nu e json}', 200));
    final result =
        await PredictionRepository(client: broken, url: 'https://exemplu/p.json').load();
    expect(result.source, DataSource.bundled);

    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString('predictions_cache'), isNull);
  });
}

/// Exceptie simpla care imita o pana de retea.
class SocketExceptionStub implements Exception {
  const SocketExceptionStub();
  @override
  String toString() => 'fara conexiune';
}

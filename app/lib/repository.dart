import 'dart:convert';

import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'config.dart';
import 'models.dart';

/// De unde au venit datele afisate acum.
enum DataSource {
  /// Descarcate acum de pe internet.
  remote,

  /// Ultima descarcare reusita, pastrata pe telefon.
  cache,

  /// Fisierul inclus in aplicatie la construire.
  bundled;

  String get label => switch (this) {
        DataSource.remote => 'descarcate de pe GitHub',
        DataSource.cache => 'salvate pe telefon',
        DataSource.bundled => 'din aplicatie',
      };
}

class LoadResult {
  const LoadResult(this.bundle, this.source);

  final PredictionBundle bundle;
  final DataSource source;
}

/// Aduce predictiile, in ordinea: internet -> ultima descarcare -> fisier inclus.
///
/// Nicio cheie API si niciun cont: `predictionsUrl` e un fisier public obisnuit.
class PredictionRepository {
  PredictionRepository({http.Client? client, String? url})
      : _client = client ?? http.Client(),
        _url = url ?? predictionsUrl;

  static const _assetPath = 'assets/predictions.json';
  static const _cacheKey = 'predictions_cache';

  final http.Client _client;
  final String _url;

  Future<LoadResult> load() async {
    final prefs = await SharedPreferences.getInstance();

    if (_url.isNotEmpty) {
      try {
        final response = await _client
            .get(Uri.parse(_url))
            .timeout(remoteTimeout);
        if (response.statusCode == 200) {
          final body = utf8.decode(response.bodyBytes);
          final bundle = _parse(body);
          // Salvam abia dupa ce stim ca se parseaza: altfel am putea cache-ui gunoi.
          await prefs.setString(_cacheKey, body);
          return LoadResult(bundle, DataSource.remote);
        }
      } catch (_) {
        // Fara internet sau server indisponibil: mergem mai departe pe datele locale.
      }

      final cached = prefs.getString(_cacheKey);
      if (cached != null) {
        try {
          return LoadResult(_parse(cached), DataSource.cache);
        } catch (_) {
          await prefs.remove(_cacheKey);
        }
      }
    }

    final raw = await rootBundle.loadString(_assetPath);
    return LoadResult(_parse(raw), DataSource.bundled);
  }

  PredictionBundle _parse(String raw) =>
      PredictionBundle.fromJson(jsonDecode(raw) as Map<String, dynamic>);
}

/// Retine cotele introduse manual de utilizator, per meci si per piata.
///
/// Cotele nu vin din niciun API platit -- tu le citesti la casa de pariuri
/// si le introduci; aplicatia calculeaza doar diferenta fata de cota corecta.
class OddsStore {
  OddsStore(this._prefs);

  final SharedPreferences _prefs;

  static Future<OddsStore> create() async =>
      OddsStore(await SharedPreferences.getInstance());

  String _key(String matchId, String market) => 'odds:$matchId:$market';

  double? read(String matchId, String market) =>
      _prefs.getDouble(_key(matchId, market));

  Future<void> write(String matchId, String market, double? value) async {
    final key = _key(matchId, market);
    if (value == null || value <= 1.0) {
      await _prefs.remove(key);
    } else {
      await _prefs.setDouble(key, value);
    }
  }
}

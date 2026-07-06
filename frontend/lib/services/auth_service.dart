import 'package:firebase_auth/firebase_auth.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:flutter/foundation.dart'; // for kIsWeb

class AuthService {
  final FirebaseAuth _auth = FirebaseAuth.instance;
  final GoogleSignIn _googleSignIn = GoogleSignIn();

  Stream<User?> get authStateChanges => _auth.authStateChanges();
  User? get currentUser => _auth.currentUser;

  Future<User?> signInWithGoogle() async {
    try {
      GoogleSignInAccount? googleUser;

      if (kIsWeb) {
        // For web, GoogleSignIn().signIn() returns a Future<GoogleSignInAccount?>
        // that can be awaited directly.
        googleUser = await _googleSignIn.signIn();
      } else {
        // For mobile, we trigger the sign-in flow.
        googleUser = await _googleSignIn.signIn();
      }
      
      if (googleUser == null) {
        // The user canceled the sign-in
        return null;
      }

      final GoogleSignInAuthentication googleAuth = await googleUser.authentication;

      final AuthCredential credential = GoogleAuthProvider.credential(
        accessToken: googleAuth.accessToken,
        idToken: googleAuth.idToken,
      );

      final UserCredential userCredential = await _auth.signInWithCredential(credential);
      print("Sapiatrum AUTH: User signed in: ${userCredential.user?.displayName}");
      return userCredential.user;

    } on FirebaseAuthException catch (e) {
      print("Sapiatrum AUTH ERROR: Firebase auth failed - ${e.message}");
      return null;
    } catch (e) {
      print("Sapiatrum AUTH ERROR: An unexpected error occurred during sign-in: $e");
      return null;
    }
  }

  Future<void> signOut() async {
    try {
      await _googleSignIn.signOut();
      await _auth.signOut();
      print("Sapiatrum AUTH: User signed out.");
    } catch (e) {
      print("Sapiatrum AUTH ERROR: An error occurred during sign-out: $e");
    }
  }
}

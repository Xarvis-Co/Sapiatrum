import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/io.dart';
import 'package:web_socket_channel/status.dart' as status;
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:firebase_auth/firebase_auth.dart';

import '../models/chat_message.dart';
import '../models/pipeline_status.dart';

class ChatService {
  final String _backendUrl = kIsWeb ? 'ws://localhost:8000/ws/chat' : 'ws://10.0.2.2:8000/ws/chat';
  IOWebSocketChannel? _channel;
  
  final _auth = FirebaseAuth.instance;
  final _firestore = FirebaseFirestore.instance;

  final StreamController<ChatMessage> _messageController = StreamController<ChatMessage>.broadcast();
  final StreamController<PipelineStatus> _statusController = StreamController<PipelineStatus>.broadcast();
  final StreamController<String> _errorController = StreamController<String>.broadcast();

  Stream<ChatMessage> get messages => _messageController.stream;
  Stream<PipelineStatus> get statusUpdates => _statusController.stream;
  Stream<String> get errors => _errorController.stream;

  void connect() {
    if (_channel != null && _channel!.closeCode == null) {
      print("Sapiatrum CHAT: Already connected.");
      return;
    }
    print("Sapiatrum CHAT: Connecting to $_backendUrl");
    try {
      _channel = IOWebSocketChannel.connect(Uri.parse(_backendUrl));
      _channel!.stream.listen(
        _handleMessage,
        onError: (error) {
          print("Sapiatrum CHAT ERROR: WebSocket error: $error");
          _errorController.add("Connection to the server failed. Please try again later.");
        },
        onDone: () {
          print("Sapiatrum CHAT: WebSocket connection closed.");
          _errorController.add("Connection to the server was lost.");
        },
      );
    } catch (e) {
      print("Sapiatrum CHAT ERROR: Failed to connect: $e");
      _errorController.add("Failed to establish connection with the server.");
    }
  }

  void _handleMessage(dynamic message) {
    print("Sapiatrum CHAT: Received raw message: $message");
    try {
      final decodedMessage = json.decode(message);
      final type = decodedMessage['type'];

      switch (type) {
        case 'status_update':
          final status = PipelineStatus.fromJson(decodedMessage);
          _statusController.add(status);
          break;
        case 'final_response':
          final data = decodedMessage['data'];
          _saveMessageToFirestore(data['content'], isUser: false, citations: data['citations']);
          break;
        case 'error':
           _errorController.add(decodedMessage['message'] ?? 'An unknown error occurred.');
          break;
        default:
          print("Sapiatrum CHAT WARNING: Unknown message type received: $type");
      }
    } catch (e) {
      print("Sapiatrum CHAT ERROR: Failed to decode or handle message: $e");
    }
  }

  Future<void> sendMessage(String text) async {
    final user = _auth.currentUser;
    if (user == null) {
      _errorController.add("You must be logged in to send a message.");
      return;
    }
    if (_channel == null || _channel!.closeCode != null) {
      _errorController.add("Not connected to the server. Please reconnect.");
      return;
    }

    // Save user's message to Firestore first
    await _saveMessageToFirestore(text, isUser: true);

    final message = {
      "question": text,
      "userId": user.uid,
    };
    
    _channel!.sink.add(json.encode(message));
    print("Sapiatrum CHAT: Sent message: $text");
  }

  Future<void> _saveMessageToFirestore(String text, {required bool isUser, Map<String, dynamic>? citations}) async {
    final user = _auth.currentUser;
    if (user == null) return;

    final messageData = {
      'text': text,
      'userId': user.uid,
      'timestamp': FieldValue.serverTimestamp(),
      'isUser': isUser,
      'citations': citations,
    };

    try {
      await _firestore
          .collection('users')
          .doc(user.uid)
          .collection('chats')
          .add(messageData);
    } catch (e) {
      print("Sapiatrum FIRESTORE ERROR: Could not save message: $e");
       _errorController.add("Failed to save message to chat history.");
    }
  }

  Stream<List<ChatMessage>> getChatHistory() {
    final user = _auth.currentUser;
    if (user == null) return Stream.value([]);

    return _firestore
        .collection('users')
        .doc(user.uid)
        .collection('chats')
        .orderBy('timestamp', descending: true)
        .snapshots()
        .map((snapshot) => snapshot.docs.map((doc) => ChatMessage.fromFirestore(doc)).toList());
  }

  void dispose() {
    _channel?.sink.close(status.normalClosure);
    _messageController.close();
    _statusController.close();
    _errorController.close();
    print("Sapiatrum CHAT: ChatService disposed.");
  }
}

import 'dart:async';
import 'package:flutter/material.dart';
import '../services/chat_service.dart';
import '../models/chat_message.dart';
import '../models/pipeline_status.dart';

class ChatViewModel extends ChangeNotifier {
  final ChatService _chatService;
  
  List<ChatMessage> _messages = [];
  PipelineStatus _status = PipelineStatus(title: "Idle", message: "Ready to receive a new task.");
  String? _error;
  bool _isLoading = false;

  late StreamSubscription<List<ChatMessage>> _messageSubscription;
  late StreamSubscription<PipelineStatus> _statusSubscription;
  late StreamSubscription<String> _errorSubscription;

  List<ChatMessage> get messages => _messages;
  PipelineStatus get status => _status;
  String? get error => _error;
  bool get isLoading => _isLoading;

  ChatViewModel(this._chatService) {
    _chatService.connect();
    
    _messageSubscription = _chatService.getChatHistory().listen((messages) {
      _messages = messages;
      _isLoading = false;
      notifyListeners();
    });

    _statusSubscription = _chatService.statusUpdates.listen((status) {
      _status = status;
      _isLoading = true; // Pipeline is running
      notifyListeners();
    });

    _errorSubscription = _chatService.errors.listen((error) {
      _error = error;
      _isLoading = false;
      notifyListeners();
      // Reset error after a delay
      Timer(const Duration(seconds: 5), () {
        _error = null;
        notifyListeners();
      });
    });
  }

  void sendMessage(String text) {
    if (text.trim().isEmpty) return;
    _isLoading = true;
    _status = PipelineStatus(title: "Sending...", message: "Transmitting task to the cluster.");
    notifyListeners();
    _chatService.sendMessage(text);
  }

  @override
  void dispose() {
    _messageSubscription.cancel();
    _statusSubscription.cancel();
    _errorSubscription.cancel();
    _chatService.dispose();
    super.dispose();
  }
}

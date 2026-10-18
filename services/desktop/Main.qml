import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: window
    width: 1120; height: 780
    minimumWidth: 850; minimumHeight: 580
    visible: true
    title: "JARVIS"
    color: "#0c1119"
    palette.window: "#111925"
    palette.base: "#182434"
    palette.button: "#26384b"
    palette.buttonText: "#e0e8f4"
    palette.text: "#e0e8f4"
    palette.windowText: "#e0e8f4"
    palette.highlight: "#367e73"
    palette.highlightedText: "#ffffff"
    palette.mid: "#34475f"
    palette.dark: "#162333"
    property var deviceOptions: JSON.parse(jarvis.devices)
    property var resultItems: []
    ListModel { id: conversation }

    Connections {
        target: jarvis
        function onMessage(speaker, body) {
            conversation.append({speaker: speaker, body: body})
            Qt.callLater(function() { chat.positionViewAtEnd() })
        }
        function onResults(value) { window.resultItems = JSON.parse(value) }
        function onCleared() { conversation.clear() }
    }
    Shortcut { sequence: "Ctrl+L"; onActivated: composer.forceActiveFocus() }
    Shortcut { sequence: "Ctrl+N"; enabled: !jarvis.busy; onActivated: jarvis.reset() }
    Shortcut {
        sequence: "Escape"
        onActivated: { if (jarvis.automatic) jarvis.setAutomatic(false, -1); else if (jarvis.recording || jarvis.status === "Transcribing") jarvis.cancelVoice(); else jarvis.stopSpeaking() }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 28
        spacing: 14

        RowLayout {
            Layout.fillWidth: true
            spacing: 14
            Rectangle {
                width: 44; height: 44; radius: 14; color: "#153a3d"
                Text { anchors.centerIn: parent; text: "J"; color: "#7ae8d5"; font.pixelSize: 25; font.bold: true }
            }
            ColumnLayout {
                spacing: 2
                Label { text: "JARVIS"; color: "#f0f5fb"; font.pixelSize: 20; font.bold: true; font.letterSpacing: 3 }
                Label { text: "Your computer, in conversation."; color: "#8493a8"; font.pixelSize: 12 }
            }
            Item { Layout.fillWidth: true }
            Rectangle {
                width: statusText.implicitWidth + 30; height: 30; radius: 15
                color: jarvis.busy ? "#263142" : "#15302d"
                Label { id: statusText; anchors.centerIn: parent; text: jarvis.status; color: jarvis.busy ? "#cad7ed" : "#89dfc4"; font.pixelSize: 12 }
            }
            Button { text: "New session"; enabled: !jarvis.busy; onClicked: jarvis.reset() }
        }

        RowLayout {
            Layout.fillWidth: true; Layout.fillHeight: true
            spacing: 20
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true
                color: "#111925"; radius: 20; border.color: "#202c3c"

                ColumnLayout {
                    visible: conversation.count === 0
                    anchors.centerIn: parent; spacing: 16
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter
                        width: 90; height: 90; radius: 45
                        color: "#163639"; border.color: "#4ba99c"; border.width: 2
                        Rectangle { anchors.centerIn: parent; width: 46; height: 46; radius: 23; color: "#79dac9"; opacity: 0.75 }
                        SequentialAnimation on opacity {
                            running: jarvis.busy; loops: Animation.Infinite
                            NumberAnimation { to: 0.4; duration: 900 }
                            NumberAnimation { to: 1; duration: 900 }
                        }
                    }
                    Label { text: "What can I help you find?"; color: "#e3ebf8"; font.pixelSize: 23; Layout.alignment: Qt.AlignHCenter }
                    Label { text: "Ask a question, find a file, or open an app.\nType below or hold the microphone to speak."; color: "#8e9db4"; horizontalAlignment: Text.AlignHCenter; lineHeight: 1.5; Layout.alignment: Qt.AlignHCenter }
                }

                ListView {
                    id: chat
                    anchors.fill: parent; anchors.margins: 22
                    model: conversation; spacing: 18; clip: true
                    ScrollBar.vertical: ScrollBar {}
                    delegate: Column {
                        required property string speaker
                        required property string body
                        width: chat.width - 12; spacing: 7
                        Label {
                            text: parent.speaker === "user" ? "YOU" : parent.speaker === "assistant" ? "JARVIS" : "NOTICE"
                            color: parent.speaker === "user" ? "#a2b6d8" : parent.speaker === "assistant" ? "#70d7c3" : "#e5be7c"
                            font.pixelSize: 10; font.letterSpacing: 1.7; font.bold: true
                        }
                        TextEdit {
                            width: parent.width
                            text: parent.body; textFormat: TextEdit.PlainText
                            readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                            color: "#e0e8f4"; selectionColor: "#2e6763"; font.pixelSize: 15
                        }
                    }
                }
            }

            Rectangle {
                visible: window.resultItems.length > 0 || jarvis.scopeNote.length > 0
                Layout.preferredWidth: 330; Layout.fillHeight: true
                color: "#111925"; radius: 20; border.color: "#202c3c"
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 18; spacing: 12
                    Label { text: jarvis.resultMode === "single" ? "SUGGESTION" : "RESULTS"; font.pixelSize: 11; font.bold: true; font.letterSpacing: 2; color: "#96a9c4" }
                    Label { text: window.resultItems.length ? (jarvis.resultMode === "single" ? "Is this the item you meant? Click to open." : "Choose an item to open it.") : "No item selected on this page."; color: "#8192a9"; font.pixelSize: 12 }
                    Label { text: jarvis.scopeNote; Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#b0b6a5"; font.pixelSize: 11 }
                    ListView {
                        id: resultsList
                        Layout.fillWidth: true; Layout.fillHeight: true
                        model: window.resultItems; spacing: 10; clip: true
                        ScrollBar.vertical: ScrollBar {}
                        delegate: Rectangle {
                            required property var modelData
                            width: resultsList.width - 10; height: resultColumn.implicitHeight + 26
                            radius: 12; color: mouse.containsMouse ? "#223448" : "#182434"
                            border.color: mouse.containsMouse ? "#4d9d93" : "#28384c"
                            Column {
                                id: resultColumn
                                anchors { left: parent.left; right: parent.right; top: parent.top; margins: 13 }
                                spacing: 6
                                Label { width: parent.width; text: modelData.number + ". " + modelData.name; color: "#e0ebf8"; wrapMode: Text.Wrap; font.pixelSize: 13; font.bold: true }
                                Label { width: parent.width; text: modelData.kind; color: "#76c7b9"; font.pixelSize: 10 }
                                Label { width: parent.width; text: modelData.location; color: "#8193ae"; font.pixelSize: 10; elide: Text.ElideMiddle }
                            }
                            MouseArea { id: mouse; anchors.fill: parent; hoverEnabled: true; enabled: !jarvis.busy; cursorShape: Qt.PointingHandCursor; onClicked: jarvis.select(modelData.number) }
                        }
                    }
                }
            }
        }

        ColumnLayout {
            Layout.fillWidth: true; spacing: 12
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 92
                color: "#101e2a"; radius: 18; border.color: "#233c4c"
                RowLayout {
                    anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 18; spacing: 16
                    VoiceOrb { phase: jarvis.voicePhase; level: jarvis.audioLevel; Layout.preferredWidth: 76; Layout.preferredHeight: 76 }
                    ColumnLayout {
                        spacing: 5
                        Label {
                            text: jarvis.voicePhase === "waiting" ? "I'm here. Start speaking."
                                : jarvis.voicePhase === "listening" ? "I'm listening\u2026"
                                : jarvis.voicePhase === "speaking" ? "JARVIS is speaking"
                                : jarvis.voicePhase === "processing" ? "Working on your request\u2026"
                                : jarvis.voicePhase === "opening" ? "Preparing your microphone\u2026" : "Let's talk"
                            color: "#e2eaf8"; font.pixelSize: 16
                        }
                        Label {
                            text: jarvis.automatic ? "Auto conversation is on \u00b7 Pause to send \u00b7 Esc to stop"
                                : "Hold to talk, or turn on Auto conversation."
                            color: "#829bb4"; font.pixelSize: 12
                        }
                    }
                    Item { Layout.fillWidth: true }
                    Switch {
                        objectName: "autoConversation"
                        text: "Auto conversation"; checked: jarvis.automatic
                        enabled: jarvis.automatic || !jarvis.busy
                        onToggled: jarvis.setAutomatic(checked, window.deviceOptions[devicePicker.currentIndex].index)
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 12
                ScrollView {
                    Layout.fillWidth: true; Layout.preferredHeight: 66
                    TextArea {
                        id: composer
                        objectName: "composer"
                        placeholderText: "Ask JARVIS…"
                        enabled: !jarvis.busy
                        color: "#e6edf7"; placeholderTextColor: "#74869f"
                        font.pixelSize: 15; wrapMode: TextArea.Wrap
                        background: Rectangle { radius: 14; color: "#182434"; border.color: composer.activeFocus ? "#65bdae" : "#2c3d54" }
                        Keys.onReturnPressed: function(event) {
                            if (!(event.modifiers & Qt.ShiftModifier)) { sendButton.clicked(); event.accepted = true }
                        }
                    }
                }
                Button {
                    id: microphone
                    objectName: "holdToTalk"
                    Layout.preferredWidth: 108; Layout.preferredHeight: 62
                    text: jarvis.recording ? "Release\nto send" : "Hold\nto talk"
                    enabled: !jarvis.automatic && (!jarvis.busy || jarvis.recording)
                    onPressed: jarvis.startVoice(window.deviceOptions[devicePicker.currentIndex].index)
                    onReleased: jarvis.finishVoice()
                    onCanceled: { if (jarvis.recording) jarvis.cancelVoice() }
                }
                Button {
                    id: sendButton
                    objectName: "sendMessage"
                    text: "Send"; Layout.preferredHeight: 62; Layout.preferredWidth: 80
                    enabled: !jarvis.busy && composer.text.trim().length > 0
                    onClicked: { if (composer.text.trim().length) { jarvis.send(composer.text); composer.clear() } }
                }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 14
                ComboBox { id: devicePicker; Layout.preferredWidth: Math.max(160, Math.min(290, window.width - 830)); model: window.deviceOptions; textRole: "name"; enabled: !jarvis.busy }
                Label { text: "Listen"; color: "#8e9db4" }
                ComboBox {
                    objectName: "recognitionLanguage"
                    Layout.preferredWidth: 110
                    model: ["English", "Türkçe", "Auto"]
                    currentIndex: ["en", "tr", "auto"].indexOf(jarvis.recognitionLanguage)
                    enabled: !jarvis.busy
                    onActivated: jarvis.setLanguage(["en", "tr", "auto"][currentIndex])
                }
                Switch { text: "Speak replies"; checked: true; onToggled: jarvis.setVoiceEnabled(checked) }
                Button { text: jarvis.automatic ? "End conversation" : jarvis.recording ? "Cancel recording" : jarvis.status === "Transcribing" ? "Cancel transcription" : "Stop voice"; onClicked: { if (jarvis.automatic) jarvis.setAutomatic(false, -1); else if (jarvis.recording || jarvis.status === "Transcribing") jarvis.cancelVoice(); else jarvis.stopSpeaking() } }
                Item { Layout.fillWidth: true }
                Label { text: "LOCAL  ·  PRIVATE"; color: "#667c96"; font.pixelSize: 10; font.letterSpacing: 1.4 }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 10
                Label { text: "Output"; color: "#8e9db4" }
                ComboBox {
                    objectName: "speechOutput"
                    Layout.fillWidth: true
                    model: JSON.parse(jarvis.outputs); textRole: "name"
                    enabled: !jarvis.busy && !jarvis.recording
                    onActivated: jarvis.setOutputDevice(model[currentIndex].index)
                }
                Label { text: "Voice"; color: "#8e9db4" }
                ComboBox {
                    objectName: "replyVoice"
                    Layout.preferredWidth: 110; model: ["English", "Türkçe"]
                    currentIndex: ["en", "tr"].indexOf(jarvis.replyLanguage)
                    enabled: !jarvis.busy && !jarvis.recording
                    onActivated: jarvis.setReplyLanguage(["en", "tr"][currentIndex])
                }
                Button {
                    objectName: "testVoice"; text: "Test voice"
                    enabled: !jarvis.busy && !jarvis.recording
                    onClicked: jarvis.testVoice()
                }
            }
            Label {
                Layout.fillWidth: true; text: [jarvis.inputNote, jarvis.recognitionNote, jarvis.outputNote].filter(function(s) { return s.length > 0 }).join("  ·  "); wrapMode: Text.Wrap
                color: "#667c96"; font.pixelSize: 10
            }
        }
    }
}

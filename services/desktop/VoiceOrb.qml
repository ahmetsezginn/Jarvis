import QtQuick

Item {
    id: orb
    objectName: "voiceOrb"
    property string phase: "idle"
    property real level: 0
    property color accent: phase === "listening" ? "#74efcf" : phase === "speaking" ? "#a895ff" : "#60bcca"
    implicitWidth: 76; implicitHeight: 76
    Rectangle { anchors.fill: parent; anchors.margins: 2; radius: width / 2; color: "#142936"; border.color: "#294955" }
    Item {
        id: orbit
        anchors.fill: parent; anchors.margins: 7
        visible: orb.phase === "waiting" || orb.phase === "opening" || orb.phase === "processing"
        Rectangle { anchors.fill: parent; radius: width / 2; color: "transparent"; border.color: orb.accent; opacity: 0.4 }
        Rectangle { width: 7; height: 7; radius: 4; color: orb.accent; anchors.horizontalCenter: parent.horizontalCenter }
        RotationAnimation on rotation { running: orbit.visible; from: 0; to: 360; duration: orb.phase === "processing" ? 1000 : 4500; loops: Animation.Infinite }
    }
    Rectangle {
        anchors.centerIn: parent; width: 25; height: 25; radius: 13
        color: orb.phase === "idle" ? "#486172" : orb.accent
        visible: orb.phase !== "listening" && orb.phase !== "speaking"
        SequentialAnimation on opacity {
            running: orb.phase === "waiting"; loops: Animation.Infinite
            NumberAnimation { to: 0.35; duration: 1200 }
            NumberAnimation { to: 0.9; duration: 1200 }
        }
    }
    Row {
        anchors.centerIn: parent; spacing: 3
        visible: orb.phase === "listening"
        Repeater {
            model: 7
            Rectangle {
                required property int index
                width: 4; radius: 2; color: orb.accent
                height: 5 + orb.level * (42 - Math.abs(index - 3) * 8)
                anchors.verticalCenter: parent.verticalCenter
                Behavior on height { NumberAnimation { duration: 100 } }
            }
        }
    }
    Item {
        id: speech
        anchors.fill: parent; anchors.margins: 16
        visible: orb.phase === "speaking"
        Repeater {
            model: 3
            Rectangle {
                required property int index
                anchors.centerIn: parent
                width: 27 + index * 5; height: 36 - index * 5; radius: width / 2
                color: ["#67dfdf", "#b899ff", "#7188ff"][index]
                opacity: 0.55; rotation: index * 60
                SequentialAnimation on scale {
                    running: speech.visible; loops: Animation.Infinite
                    NumberAnimation { to: 0.75; duration: 470 + index * 100; easing.type: Easing.InOutSine }
                    NumberAnimation { to: 1.15; duration: 470 + index * 100; easing.type: Easing.InOutSine }
                }
            }
        }
        RotationAnimation on rotation { running: speech.visible; from: 0; to: 360; duration: 3400; loops: Animation.Infinite }
    }
}

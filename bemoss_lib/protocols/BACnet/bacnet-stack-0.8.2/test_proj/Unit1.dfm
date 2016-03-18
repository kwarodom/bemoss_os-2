object Form1: TForm1
  Left = 279
  Top = 153
  Width = 1142
  Height = 656
  Caption = 'Form1'
  Color = clBtnFace
  Font.Charset = DEFAULT_CHARSET
  Font.Color = clWindowText
  Font.Height = -11
  Font.Name = 'MS Sans Serif'
  Font.Style = []
  OldCreateOrder = False
  PixelsPerInch = 96
  TextHeight = 13
  object MSComm1: TMSComm
    Left = 352
    Top = 96
    Width = 32
    Height = 32
    ControlData = {
      2143341208000000ED030000ED03000001568A64000006000000040000040000
      00020000802500000000080000000000000000003F00000001000000}
  end
  object Button1: TButton
    Left = 288
    Top = 232
    Width = 75
    Height = 25
    Caption = 'Start'
    TabOrder = 1
    OnClick = Button1Click
  end
  object Button2: TButton
    Left = 416
    Top = 232
    Width = 75
    Height = 25
    Caption = 'Stop'
    TabOrder = 2
    OnClick = Button2Click
  end
end

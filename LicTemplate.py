from Model import *
from LicUndoActions import *

class TemplateLineItem(object):

    def formatBorder(self, fillColor = False):
        
        self.setSelected(False)  # Deselect to better see new border changes
        parentWidget = self.scene().views()[0]
        stack = self.scene().undoStack
        dialog = LicDialogs.PenDlg(parentWidget, self.pen(), hasattr(self, 'cornerRadius'), fillColor)
        
        penAction = lambda newPen: stack.push(SetPenCommand(self, self.pen(), newPen))
        parentWidget.connect(dialog, SIGNAL("changed"), penAction)
        
        brushAction = lambda newBrush: stack.push(SetBrushCommand(self, self.brush(), newBrush))
        parentWidget.connect(dialog, SIGNAL("brushChanged"), brushAction)
        parentWidget.connect(dialog, SIGNAL("reset"), self.resetAction)
        
        # TODO: Try messing with the undo stack index to see if we can avoid the 'undo cancel' annoyance
        stack.beginMacro("change Border")
        dialog.exec_()
        stack.endMacro()
    
    def resetAction(self):
        pass
    
class TemplateRectItem(TemplateLineItem):
    """ Encapsulates functionality common to all template GraphicItems, like formatting border & fill""" 

    def postLoadInit(self, dataText):
        self.data = lambda index: dataText
        self.setFlags(NoMoveFlags)
    
    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Format Border", self.formatBorder)
        menu.addAction("Background Color", self.setBackgroundColor)
        menu.addAction("Background Gradient", self.setBackgroundGradient)
        menu.addAction("Background None", self.setBackgroundNone)
        menu.exec_(event.screenPos())

    def setBackgroundColor(self):
        color, value = QColorDialog.getRgba(self.brush().color().rgba(), self.scene().views()[0])
        color = QColor.fromRgba(color)
        if color.isValid():
            self.scene().undoStack.push(SetBrushCommand(self, self.brush(), QBrush(color)))
    
    def setBackgroundNone(self):
        self.scene().undoStack.push(SetBrushCommand(self, self.brush(), QBrush(Qt.transparent)))
        
    def setBackgroundGradient(self):
        g = self.brush().gradient()
        dialog = GradientDialog.GradientDialog(self.scene().views()[0], self.rect().size().toSize(), g)
        if dialog.exec_():
            self.scene().undoStack.push(SetBrushCommand(self, self.brush(), QBrush(dialog.getGradient())))

class TemplatePage(Page):

    def __init__(self, subModel, instructions):
        Page.__init__(self, subModel, instructions, 0, 0)
        self.__filename = None
        self.dataText = "Template Page"
        self.subModelPart = None

    def __getFilename(self):
        return self.__filename
        
    def __setFilename(self, filename):
        self.__filename = filename
        self.dataText = "Template - " + os.path.basename(self.filename)
        
    filename = property(fget = __getFilename, fset = __setFilename)

    def postLoadInit(self, filename):
        # TemplatePages are rarely instantiated directly - instead, they're regular Page
        # instances promoted to TemplatePages by changing their __class__.  Doing that does
        # *not* call TemplatePage.__init__, so, can explicitly call postLoadInit instead. 

        self.filename = filename
        self.prevPage = lambda: None
        self.nextPage = lambda: None
        self.data = lambda index: self.dataText

        # Promote page members to appropriate Template subclasses, and initialize if necessary
        step = self.steps[0]
        step.__class__ = TemplateStep
        step.postLoadInit()
        if step.pli:
            step.pli.__class__ = TemplatePLI
        if self.submodelItem:
            self.submodelItem.__class__ = TemplateSubmodelPreview
        if step.callouts:
            step.callouts[0].__class__ = TemplateCallout
            step.callouts[0].arrow.__class__ = TemplateCalloutArrow
                
        self.numberItem.setAllFonts = lambda oldFont, newFont: self.scene().undoStack.push(SetItemFontsCommand(self, oldFont, newFont, 'Page'))
        step.numberItem.setAllFonts = lambda oldFont, newFont: self.scene().undoStack.push(SetItemFontsCommand(self, oldFont, newFont, 'Step'))
        self.numberItem.contextMenuEvent = lambda event: self.fontMenuEvent(event, self.numberItem)
        step.numberItem.contextMenuEvent = lambda event: self.fontMenuEvent(event, step.numberItem)

        if step.hasPLI():
            for item in step.pli.pliItems:
                item.numberItem.setAllFonts = lambda oldFont, newFont: self.scene().undoStack.push(SetItemFontsCommand(self, oldFont, newFont, 'PLI Item'))
                item.numberItem.contextMenuEvent = lambda event, i = item: self.fontMenuEvent(event, i.numberItem)
        
        # Set all page elements so they can't move
        for item in self.getAllChildItems():
            item.setFlags(NoMoveFlags)

    def createBlankTemplate(self, glContext):
        step = Step(self, 0)
        step.data = lambda index: "Template Step"
        self.addStep(step)
        
        self.subModelPart = Submodel()
        for part in self.subModel.parts[:5]:
            step.addPart(part.duplicate())
            self.subModelPart.parts.append(part)

        self.subModelPart.createOGLDisplayList()
        self.initOGLDimension(self.subModelPart, glContext)
        
        step.csi.createOGLDisplayList()
        self.initOGLDimension(step.csi, glContext)

        self.addSubmodelImage()
        self.submodelItem.setPartOGL(self.subModelPart)
        
        self.initLayout()
        self.postLoadInit("dynamic_template.lit")

    def initOGLDimension(self, part, glContext):

        glContext.makeCurrent()
        for size in [512, 1024, 2048]:
            # Create a new buffer tied to the existing GLWidget, to get access to its display lists
            pBuffer = QGLPixelBuffer(size, size, getGLFormat(), glContext)
            pBuffer.makeCurrent()

            # Render CSI and calculate its size
            if part.initSize(size, pBuffer):
                break
        glContext.makeCurrent()
        
    def applyFullTemplate(self):
        
        originalPage = self.instructions.mainModel.pages[0]
        stack = self.scene().undoStack
        stack.beginMacro("Load Template")
        stack.push(SetPageBackgroundColorCommand(self, originalPage.color, self.color))
        stack.push(SetPageBackgroundBrushCommand(self, originalPage.brush, self.brush))
        
        stack.push(SetItemFontsCommand(self, originalPage.numberItem.font(), self.numberItem.font(), 'Page'))
        stack.push(SetItemFontsCommand(self, originalPage.steps[0].numberItem.font(), self.steps[0].numberItem.font(), 'Step'))
        stack.push(SetItemFontsCommand(self, originalPage.steps[0].pli.pliItems[0].numberItem.font(), self.steps[0].pli.pliItems[0].numberItem.font(), 'PLI Item'))

        step = self.steps[0]
        if step.pli:
            stack.push(SetPenCommand(step.pli, originalPage.steps[0].pli.pen(), step.pli.pen()))
            stack.push(SetBrushCommand(step.pli, originalPage.steps[0].pli.brush(), step.pli.brush()))
        
        if self.submodelItem:
            stack.push(SetPenCommand(self.submodelItem, originalPage.submodelItem.pen(), self.submodelItem.pen()))
            stack.push(SetBrushCommand(self.submodelItem, originalPage.submodelItem.brush(), self.submodelItem.brush()))

        stack.endMacro()

    def applyDefaults(self):
        
        step = self.steps[0]
        Page.defaultColor = self.color
        Page.defaultBrush = self.brush
        if step.pli:
            PLI.defaultPen = step.pli.pen()
            PLI.defaultBrush = step.pli.brush()
        if step.callouts:
            Callout.defaultPen = step.callouts[0].pen()
            Callout.defaultBrush = step.callouts[0].brush()
        if self.submodelItem:
            SubmodelPreview.defaultPen = self.submodelItem.pen()
            SubmodelPreview.defaultBrush = self.submodelItem.brush()
    
    def getStep(self, number):
        return self.steps[0] if number == 0 else None

    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Background Color", self.setBackgroundColor)
        arrowMenu = menu.addMenu("Background Fill Effect")
        arrowMenu.addAction("Gradient", self.setBackgroundGradient)
        arrowMenu.addAction("Image", self.setBackgroundImage)
        arrowMenu.addAction("None", self.setBackgroundNone)
        #menu.addSeparator()
        menu.exec_(event.screenPos())
        
    def setColor(self, color):
        Page.defaultColor = color
        self.color = color
        
    def setBrush(self, brush):
        Page.defaultBrush = brush
        self.brush = brush
        
    def setBackgroundColor(self):
        color = QColorDialog.getColor(self.color, self.scene().views()[0])
        if color.isValid(): 
            self.scene().undoStack.push(SetPageBackgroundColorCommand(self, self.color, color))
    
    def setBackgroundNone(self):
        self.scene().undoStack.push(SetPageBackgroundBrushCommand(self, self.brush, None))
        
    def setBackgroundGradient(self):
        g = self.brush.gradient() if self.brush else None
        dialog = GradientDialog.GradientDialog(self.scene().views()[0], Page.PageSize, g)
        if dialog.exec_():
            self.scene().undoStack.push(SetPageBackgroundBrushCommand(self, self.brush, QBrush(dialog.getGradient())))
    
    def setBackgroundImage(self):
        
        parentWidget = self.scene().views()[0]
        filename = QFileDialog.getOpenFileName(parentWidget, "Open Background Image", QDir.currentPath())
        if filename.isEmpty():
            return
        
        image = QImage(filename)
        if image.isNull():
            QMessageBox.information(self, "Lic", "Cannot load " + filename)
            return

        stack = self.scene().undoStack
        dialog = LicDialogs.BackgroundImagePropertiesDlg(parentWidget, image, self.color, self.brush, Page.PageSize)
        action = lambda image: stack.push(SetPageBackgroundBrushCommand(self, self.brush, QBrush(image) if image else None))
        parentWidget.connect(dialog, SIGNAL("changed"), action)

        stack.beginMacro("change Page background")
        dialog.exec_()
        stack.endMacro()

    def fontMenuEvent(self, event, item):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Set Font", lambda: self.setItemFont(item))
        menu.exec_(event.screenPos())
        
    def setItemFont(self, item):
        oldFont = item.font()
        newFont, ok = QFontDialog.getFont(oldFont)
        if ok:
            item.setAllFonts(oldFont, newFont)

class TemplateCalloutArrow(TemplateLineItem, CalloutArrow):
    
    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Format Border", lambda: self.formatBorder(self.brush().color()))
        menu.exec_(event.screenPos())

    def setPen(self, newPen):
        CalloutArrow.setPen(self, newPen)
        CalloutArrow.defaultPen = newPen

    def setBrush(self, newBrush):
        CalloutArrow.setBrush(self, newBrush)
        CalloutArrow.defaultBrush = newBrush
        
class TemplateCallout(TemplateRectItem, Callout):
    
    def setPen(self, newPen):
        Callout.setPen(self, newPen)
        Callout.defaultPen = newPen

    def setBrush(self, newBrush):
        Callout.setBrush(self, newBrush)
        Callout.defaultBrush = newBrush

class TemplatePLI(TemplateRectItem, PLI):
    
    def setPen(self, newPen):
        PLI.setPen(self, newPen)
        PLI.defaultPen = newPen

    def setBrush(self, newBrush):
        PLI.setBrush(self, newBrush)
        PLI.defaultBrush = newBrush

class TemplateSubmodelPreview(TemplateRectItem, SubmodelPreview):

    def setPen(self, newPen):
        SubmodelPreview.setPen(self, newPen)
        SubmodelPreview.defaultPen = newPen

    def setBrush(self, newBrush):
        SubmodelPreview.setBrush(self, newBrush)
        SubmodelPreview.defaultBrush = newBrush

class TemplateStep(Step):
    
    def postLoadInit(self):
        self.data = lambda index: "Template Step"
        self.setFlags(NoMoveFlags)
    
    def contextMenuEvent(self, event):
        menu = QMenu(self.scene().views()[0])
        menu.addAction("Disable PLIs" if self.hasPLI() else "Enable PLIs", self.togglePLIs)
        #menu.addSeparator()
        menu.addAction("Format Background", self.formatBackground)
        arrowMenu = menu.addMenu("Format Background")
        #arrowMenu.addAction("Color", self.setBackgroundColor)
        #arrowMenu.addAction("Gradient", self.setBackgroundColor)
        #rrowMenu.addAction("Image", self.setBackgroundColor)
        menu.exec_(event.screenPos())

    def togglePLIs(self):
        self.scene().undoStack.push(TogglePLIs(self, not self.hasPLI()))
    
    def formatBackground(self):
        pass
    
    